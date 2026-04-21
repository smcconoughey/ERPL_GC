#!/usr/bin/env python3
"""
DAQ Streamer v2 — NI-DAQmx → Node.js via TCP

Key changes from v1:
  - Per-device reader threads; each drains its own task independently
  - Always uses CURRENT_READ_POSITION — no more MOST_RECENT_SAMPLE stepping
  - TDMS driver-level logging for hardware-timed devices (PT, LC):
      NI-DAQmx writes to disk at the hardware rate; Python never touches
      individual log samples
  - TC (NI-9211) stays on-demand at ~1 Hz with a tiny CSV log
  - UI broadcast is a separate thread running at TARGET_SEND_HZ, completely
      decoupled from acquisition rate
  - Status file written on a 5-second timer, not per row
  - deque used everywhere a queue is needed (no O(n) list.pop(0))
"""

import csv
import json
import logging
import signal
import socket
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import nidaqmx
import nidaqmx.system
from nidaqmx.constants import (
    AcquisitionType,
    LoggingMode,
    LoggingOperation,
    ReadRelativeTo,
)

from config import (
    ACTIVE_DEVICES,
    DEBUG_ENABLE,
    DEBUG_RAW_SUMMARY,
    DEBUG_SAMPLE_EVERY_N,
    DEVICE_CHASSIS,
    LC_MODULE_SLOT,
    MODULE_SLOT,
    NODE_HOST,
    NODE_TCP_PORT,
    PT_MODULE_SLOT,
    SAMPLES_PER_READ,
    TARGET_SAMPLE_HZ,
    TARGET_SEND_HZ,
    TC_MODULE_SLOT,
)
from devices.device_registry import DeviceRegistry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_raw(raw: Any, channel_count: int) -> List[List[float]]:
    """Coerce whatever nidaqmx.Task.read() returns into List[List[float]]."""
    if isinstance(raw, (int, float)):
        result = [[float(raw)]]
        while len(result) < channel_count:
            result.append([])
        return result

    if not isinstance(raw, list) or not raw:
        return [[] for _ in range(channel_count)]

    # Single sample per channel → list of scalars
    if not isinstance(raw[0], list):
        result = [[float(v)] for v in raw[:channel_count]]
        while len(result) < channel_count:
            result.append([])
        return result

    # Already list-of-lists (N channels × M samples)
    result = [list(ch) for ch in raw[:channel_count]]
    while len(result) < channel_count:
        result.append([])
    return result


# ---------------------------------------------------------------------------
# DeviceReader — one per hardware-timed device
# ---------------------------------------------------------------------------

class DeviceReader:
    """
    Reads one hardware-timed NI-DAQmx task in a dedicated background thread.

    The read call blocks inside nidaqmx until `samples_per_read` fresh samples
    are available, so the thread naturally runs at:
        drain_hz = hardware_rate / samples_per_read

    At 1 kHz hardware rate and SAMPLES_PER_READ=50 that is 20 Hz — only
    20 network round trips/sec over the 300 ft Ethernet run.

    CURRENT_READ_POSITION advances the buffer cursor after each read so every
    sample is consumed exactly once. No duplicates, no gaps (as long as the
    drain rate keeps up with the hardware).

    TDMS logging (when enabled) is configured on the underlying task via
    configure_logging(). The NI-DAQmx C driver writes samples to disk at the
    full hardware rate; Python reads back the same data for UI snapshots via
    LOG_AND_READ mode. Python never touches the log file directly.

    Tare requests arrive from the broadcast/command thread via request_tare()
    and are applied on the next read cycle inside this thread — no cross-thread
    writes to device state.
    """

    def __init__(self, device: Any, task: nidaqmx.Task, samples_per_read: int):
        self._device = device
        self._task = task
        self._samples_per_read = samples_per_read

        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

        self._snapshot_lock = threading.Lock()
        self._snapshot: Optional[Dict[str, Any]] = None

        self._tare_lock = threading.Lock()
        self._tare_all = False
        self._tare_channels: List[int] = []

        self._read_count = 0
        self.latest_raw: List[List[float]] = []

        # Latency monitoring (bounded deque — no pop(0))
        self._latencies: deque = deque(maxlen=200)

    # ── Public API ───────────────────────────────────────────────────────

    @property
    def device(self) -> Any:
        return self._device

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def request_tare(self, channels: Optional[List[int]] = None) -> None:
        """Thread-safe tare request. channels=None means tare all."""
        with self._tare_lock:
            if channels is None:
                self._tare_all = True
            else:
                self._tare_channels.extend(channels)

    def get_snapshot(self) -> Optional[Dict[str, Any]]:
        with self._snapshot_lock:
            return self._snapshot

    def start(self) -> None:
        self._stop.clear()
        name = f"reader-{self._device.device_info['device_type']}"
        self._thread = threading.Thread(target=self._read_loop, name=name, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5.0)

    # ── Read loop ────────────────────────────────────────────────────────

    def _configure_stream(self) -> None:
        try:
            self._task.in_stream.read_relative_to = ReadRelativeTo.CURRENT_READ_POSITION
            self._task.in_stream.offset = 0
        except Exception as e:
            logger.warning(f"{self._device.device_info['device_type']}: could not set CURRENT_READ_POSITION: {e}")

    def _read_loop(self) -> None:
        dtype = self._device.device_info['device_type']
        logger.info(f"{dtype}: reader started  samples_per_read={self._samples_per_read}")

        self._configure_stream()
        consecutive_errors = 0

        while not self._stop.is_set():
            t0 = time.perf_counter()
            try:
                raw = self._task.read(
                    number_of_samples_per_channel=self._samples_per_read,
                    timeout=2.0,
                )
                consecutive_errors = 0

            except nidaqmx.DaqError as e:
                msg = str(e)
                if '-200279' in msg or 'keep up with the hardware' in msg:
                    # Buffer overrun: we fell behind the hardware.
                    # Drain everything available, then resume normal reads.
                    logger.warning(f"{dtype}: buffer overrun — draining with READ_ALL_AVAILABLE")
                    try:
                        self._configure_stream()
                        raw = self._task.read(
                            number_of_samples_per_channel=nidaqmx.constants.READ_ALL_AVAILABLE,
                            timeout=1.0,
                        )
                    except Exception as drain_err:
                        logger.error(f"{dtype}: drain failed: {drain_err}")
                        consecutive_errors += 1
                        time.sleep(0.1)
                        continue
                elif '-200277' in msg or 'Invalid combination of position' in msg:
                    # Stale position reference; reset and retry
                    self._configure_stream()
                    consecutive_errors += 1
                    time.sleep(0.05)
                    continue
                else:
                    consecutive_errors += 1
                    logger.error(f"{dtype}: DAQ error: {e}")
                    if consecutive_errors > 10:
                        logger.error(f"{dtype}: too many consecutive errors, stopping reader")
                        break
                    time.sleep(0.05)
                    continue

            except Exception as e:
                consecutive_errors += 1
                logger.error(f"{dtype}: unexpected error: {e}")
                if consecutive_errors > 10:
                    break
                time.sleep(0.05)
                continue

            # Track read latency
            latency = time.perf_counter() - t0
            self._latencies.append(latency)

            # Normalize → List[List[float]]
            dev_raw = _normalize_raw(raw, self._device.channel_count)
            self.latest_raw = dev_raw

            # Apply any pending tare requests inside this thread
            self._apply_tare(dev_raw)

            # Process for UI snapshot
            processed = self._device.process_data(dev_raw)
            processed['timestamp'] = time.time()
            processed['source'] = dtype
            processed['sample_count'] = sum(
                len(ch) for ch in dev_raw if isinstance(ch, list)
            )

            with self._snapshot_lock:
                self._snapshot = processed
                self._read_count += 1

            if (DEBUG_ENABLE and DEBUG_RAW_SUMMARY
                    and self._read_count % max(1, DEBUG_SAMPLE_EVERY_N) == 0):
                for ch_idx, ch_data in enumerate(dev_raw[:8]):
                    if ch_data:
                        avg = sum(ch_data) / len(ch_data)
                        logger.info(f"{dtype} ch{ch_idx:02d} avg={avg:.6f} n={len(ch_data)}")

        logger.info(f"{dtype}: reader stopped  total_reads={self._read_count}")

    def _apply_tare(self, dev_raw: List[List[float]]) -> None:
        with self._tare_lock:
            if self._tare_all:
                if hasattr(self._device, 'tare'):
                    try:
                        self._device.tare(dev_raw)
                        logger.info(f"Tare: {self._device.device_info['device_type']}")
                    except Exception as e:
                        logger.warning(f"Tare failed: {e}")
                self._tare_all = False
                self._tare_channels.clear()
            elif self._tare_channels:
                if hasattr(self._device, 'tare_channels'):
                    try:
                        self._device.tare_channels(list(self._tare_channels), dev_raw)
                    except Exception as e:
                        logger.warning(f"Targeted tare failed: {e}")
                self._tare_channels.clear()


# ---------------------------------------------------------------------------
# DAQStreamer
# ---------------------------------------------------------------------------

class DAQStreamer:
    """
    Top-level coordinator.

    Thread layout:
      main thread    — command loop (polls .cmd files, blocks until shutdown)
      reader-PT      — DeviceReader for NI-9208 PT card
      reader-LC      — DeviceReader for NI-9237 LC card
      reader-TC      — on-demand reads for NI-9211 TC card (~1 Hz)
      broadcast      — merges latest snapshots, sends JSON to Node
    """

    def __init__(self) -> None:
        self.node_host = NODE_HOST
        self.node_port = NODE_TCP_PORT
        self.running = False
        self.devices: List[Any] = []

        # Per-device reader threads (PT, LC)
        self._readers: List[DeviceReader] = []
        self._device_tasks: List[Tuple[Any, nidaqmx.Task]] = []

        # TC on-demand
        self._tc_device: Optional[Any] = None
        self._tc_stop = threading.Event()
        self._tc_thread: Optional[threading.Thread] = None
        self._tc_lock = threading.Lock()
        self._tc_snapshot: Optional[Dict[str, Any]] = None

        # Broadcast
        self._broadcast_thread: Optional[threading.Thread] = None

        # Logging state
        self.logging_enabled = False
        self._log_start_time: Optional[float] = None
        self._log_dir: Optional[Path] = None
        self._tdms_active: Dict[str, bool] = {}   # dtype → whether TDMS is live
        self._tdms_paths: Dict[str, Path] = {}

        # TC CSV (low rate — TDMS not applicable for on-demand devices)
        self._tc_csv_file = None
        self._tc_csv_writer = None
        self._tc_csv_rows = 0
        self._log_lock = threading.Lock()

        # Status file — written on a 5 s timer, never per row
        self._status_file = Path(__file__).parent / 'logging_status.json'
        self._last_status_write = 0.0

        # Command files
        _d = Path(__file__).parent
        self.start_log_cmd = _d / 'start_logging.cmd'
        self.stop_log_cmd = _d / 'stop_logging.cmd'
        self.shutdown_cmd = _d / 'shutdown_daq.cmd'
        self.tare_cmd_file = _d / 'tare.cmd'
        self.tare_lc_cmd_file = _d / 'tare_lc.cmd'
        self.tare_pt_cmd_file = _d / 'tare_pt.cmd'
        self._tare_config_file = _d / 'tare_config.json'

        # Node TCP socket
        self._node_socket: Optional[socket.socket] = None
        self._socket_lock = threading.Lock()

        self._initialize_devices()

    # ── Device init ──────────────────────────────────────────────────────

    def _initialize_devices(self) -> None:
        slots = {
            'pt_card': PT_MODULE_SLOT,
            'lc_card': LC_MODULE_SLOT,
            'tc_card': TC_MODULE_SLOT,
        }
        for name in ACTIVE_DEVICES:
            slot = slots.get(name, MODULE_SLOT)
            try:
                device = DeviceRegistry.create_device(name, DEVICE_CHASSIS, module_slot=slot)
                # Push TARGET_SAMPLE_HZ into hardware-timed devices so they
                # configure_timing at the right rate.
                if not getattr(device, 'on_demand', False):
                    device.sample_rate = TARGET_SAMPLE_HZ
                self.devices.append(device)
                logger.info(f"Initialized {device.device_info['device_type']}: {device.module_name}")
            except Exception as e:
                logger.error(f"Failed to initialize {name}: {e}")

    # ── Main entry ───────────────────────────────────────────────────────

    def run(self) -> None:
        self.running = True
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)
        try:
            self._start_acquisition()
            self._command_loop()
        finally:
            self._stop_acquisition()

    def stop(self) -> None:
        self.running = False

    def _on_signal(self, sig, _frame) -> None:
        logger.info(f"Signal {sig} — shutting down")
        self.running = False

    # ── Acquisition ──────────────────────────────────────────────────────

    def _start_acquisition(self) -> None:
        hw_timed = [d for d in self.devices if not getattr(d, 'on_demand', False)]
        on_demand = [d for d in self.devices if getattr(d, 'on_demand', False)]

        if on_demand:
            self._tc_device = on_demand[0]

        # Identify PT and LC for the start-trigger wire
        pt_dev = next(
            (d for d in hw_timed if 'pt' in d.device_info['device_type'].lower()), None
        )
        lc_dev = next(
            (d for d in hw_timed if 'lc' in d.device_info['device_type'].lower()), None
        )

        # Reset hardware to clear any reserved resources from a previous run
        self._reset_devices(hw_timed)

        # Build tasks
        for device in hw_timed:
            task = nidaqmx.Task()
            device.configure_channels(task)
            device.configure_timing(task)

            # Wire LC to start when PT triggers — aligns t=0 across cards.
            # After that each card runs at its own hardware rate independently;
            # TDMS timestamps handle post-hoc alignment.
            if device is lc_dev and pt_dev is not None:
                try:
                    trig_src = f"/{pt_dev.module_name}/StartTrigger"
                    task.triggers.start_trigger.cfg_dig_edge_start_trig(trig_src)
                    logger.info(f"LC start-trigger → {trig_src}")
                except Exception as e:
                    logger.warning(f"Could not wire LC start-trigger: {e} — running free")

            # Bridge offset nulling for LC (no load applied at startup)
            if device is lc_dev and hasattr(device, 'perform_bridge_offset_nulling'):
                try:
                    device.perform_bridge_offset_nulling(task)
                except Exception as e:
                    logger.warning(f"Bridge offset nulling skipped: {e}")

            spr = self._samples_per_read_for(device)
            reader = DeviceReader(device, task, spr)
            self._readers.append(reader)
            self._device_tasks.append((device, task))

        # Start PT first (it is the master clock / trigger source for LC)
        def _start_reader(reader: DeviceReader) -> None:
            reader._task.start()
            logger.info(
                f"Started {reader.device.device_info['device_type']} "
                f"@ {getattr(reader.device, 'sample_rate', '?')} Hz  "
                f"samples_per_read={reader._samples_per_read}"
            )
            reader.start()

        for reader in self._readers:
            if 'pt' in reader.device.device_info['device_type'].lower():
                _start_reader(reader)

        for reader in self._readers:
            if 'pt' not in reader.device.device_info['device_type'].lower():
                _start_reader(reader)

        # TC on-demand thread
        if self._tc_device:
            self._tc_stop.clear()
            self._tc_thread = threading.Thread(
                target=self._tc_read_loop, name="reader-TC", daemon=True
            )
            self._tc_thread.start()

        # Broadcast thread
        self._broadcast_thread = threading.Thread(
            target=self._broadcast_loop, name="broadcast", daemon=True
        )
        self._broadcast_thread.start()
        logger.info("Acquisition started")

    def _samples_per_read_for(self, device: Any) -> int:
        """
        Choose samples_per_read so the reader drains at ~TARGET_SEND_HZ.

        The NI-9237 (LC) may coerce to ~1613 Hz in HIGH_SPEED mode.
        After configure_timing(), device.sample_rate holds the actual
        hardware rate. We read it here (post-configure) so we get the
        real coerced value, not our requested rate.
        """
        rate = float(getattr(device, 'sample_rate', TARGET_SAMPLE_HZ))
        if rate <= 0:
            return SAMPLES_PER_READ
        # Drain at the configured TARGET_SEND_HZ but no faster than 25 Hz
        # (faster would mean very small chunks and more network overhead)
        drain_hz = min(float(TARGET_SEND_HZ), 25.0)
        n = max(1, int(round(rate / drain_hz)))
        logger.info(
            f"{device.device_info['device_type']}: "
            f"rate={rate:.1f} Hz  drain={drain_hz:.0f} Hz  samples_per_read={n}"
        )
        return min(n, 2000)

    def _reset_devices(self, devices: List[Any]) -> None:
        """Reset NI modules to clear reserved resources from a prior run."""
        try:
            system = nidaqmx.system.System.local()
            names = []
            for d in devices:
                n = getattr(d, 'module_name', None)
                if n and n not in names:
                    names.append(n)
            for name in names:
                try:
                    system.devices[name].reset_device()
                    logger.info(f"Reset {name}")
                    time.sleep(0.15)
                except Exception:
                    pass
            time.sleep(3.0)  # allow Ethernet chassis to settle
        except Exception as e:
            logger.warning(f"Device reset skipped: {e}")

    def _stop_acquisition(self) -> None:
        if self.logging_enabled:
            self.stop_logging()

        for reader in self._readers:
            reader.stop()

        self._tc_stop.set()
        if self._tc_thread:
            self._tc_thread.join(timeout=3.0)

        for _, task in self._device_tasks:
            try:
                task.stop()
            except Exception:
                pass
            try:
                task.close()
            except Exception:
                pass
        self._device_tasks.clear()
        self._readers.clear()

        self._close_node_socket()
        logger.info("Acquisition stopped")

    # ── TC on-demand thread ──────────────────────────────────────────────

    def _tc_read_loop(self) -> None:
        """
        NI-9211 does not support hardware sample clock timing.
        Each read creates a fresh one-shot task.  Max rate ~14 S/s aggregate
        so we poll at ~1 Hz.
        """
        logger.info("TC reader thread started (~1 Hz on-demand)")
        while not self._tc_stop.is_set():
            try:
                with nidaqmx.Task() as task:
                    self._tc_device.configure_channels(task)
                    raw = task.read(number_of_samples_per_channel=1, timeout=5.0)
                dev_raw = _normalize_raw(raw, self._tc_device.channel_count)
                processed = self._tc_device.process_data(dev_raw)
                processed['timestamp'] = time.time()
                processed['source'] = self._tc_device.device_info['device_type']
                with self._tc_lock:
                    self._tc_snapshot = processed
                if self.logging_enabled:
                    self._write_tc_csv(processed)
            except Exception as e:
                logger.warning(f"TC read error: {e}")
            self._tc_stop.wait(timeout=1.0)
        logger.info("TC reader thread stopped")

    # ── Broadcast loop ───────────────────────────────────────────────────

    def _broadcast_loop(self) -> None:
        """
        Runs at TARGET_SEND_HZ.  Reads the latest snapshot from each reader
        and sends a merged JSON frame to Node.  This thread never touches the
        NI-DAQmx tasks — it is purely a consumer of already-processed data.
        """
        interval = 1.0 / max(1.0, float(TARGET_SEND_HZ))
        logger.info(f"Broadcast loop started at {TARGET_SEND_HZ:.0f} Hz")

        while self.running:
            t0 = time.monotonic()

            pt_channels, lc_channels, tc_channels = [], [], []
            for reader in self._readers:
                snap = reader.get_snapshot()
                if snap is None:
                    continue
                channels = snap.get('channels', [])
                if not channels:
                    continue
                first = channels[0]
                if 'pressure_psi' in first:
                    pt_channels = channels
                elif 'lbf' in first or 'v_per_v' in first:
                    lc_channels = channels

            with self._tc_lock:
                if self._tc_snapshot:
                    tc_channels = self._tc_snapshot.get('channels', [])

            merged = {
                'type': 'merged_frame',
                'timestamp': time.time(),
                'pt': pt_channels,
                'lc': lc_channels,
                'tc': tc_channels,
            }
            try:
                self.send_to_node_sync(merged)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")

            # Status file on a 5 s timer
            now = time.monotonic()
            if now - self._last_status_write >= 5.0:
                self._write_status_file()
                self._last_status_write = now

            elapsed = time.monotonic() - t0
            sleep_for = interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)

    # ── Command loop (main thread) ───────────────────────────────────────

    def _command_loop(self) -> None:
        while self.running:
            try:
                # Logging control
                if self.start_log_cmd.exists() and not self.logging_enabled:
                    self.start_logging()
                    self.start_log_cmd.unlink(missing_ok=True)
                if self.stop_log_cmd.exists() and self.logging_enabled:
                    self.stop_logging()
                    self.stop_log_cmd.unlink(missing_ok=True)

                # Shutdown
                if self.shutdown_cmd.exists():
                    logger.info("Shutdown command received")
                    self.running = False
                    self.shutdown_cmd.unlink(missing_ok=True)
                    break

                # Tare
                tare_all = self.tare_cmd_file.exists()
                tare_lc = self.tare_lc_cmd_file.exists()
                tare_pt = self.tare_pt_cmd_file.exists()
                if tare_all or tare_lc or tare_pt:
                    self._dispatch_tare(tare_all=tare_all, tare_lc=tare_lc, tare_pt=tare_pt)
                    for f in (self.tare_cmd_file, self.tare_lc_cmd_file, self.tare_pt_cmd_file):
                        f.unlink(missing_ok=True)

            except Exception as e:
                logger.error(f"Command loop error: {e}")

            time.sleep(0.25)

    # ── Tare dispatch ────────────────────────────────────────────────────

    def _dispatch_tare(self, tare_all=False, tare_lc=False, tare_pt=False) -> None:
        targeted_pt: List[int] = []
        targeted_lc: List[int] = []
        try:
            if self._tare_config_file.exists():
                cfg = json.loads(self._tare_config_file.read_text())
                targeted_pt = [int(c) for c in cfg.get('pt_channels', [])]
                targeted_lc = [int(c) for c in cfg.get('lc_channels', [])]
                self._tare_config_file.unlink(missing_ok=True)
        except Exception:
            pass

        for reader in self._readers:
            dt = reader.device.device_info['device_type'].lower()
            is_pt = 'pt' in dt
            is_lc = 'lc' in dt

            if tare_all:
                reader.request_tare()
            else:
                if is_pt and tare_pt:
                    reader.request_tare()
                if is_lc and tare_lc:
                    reader.request_tare()

            if is_pt and targeted_pt:
                reader.request_tare(channels=targeted_pt)
            if is_lc and targeted_lc:
                reader.request_tare(channels=targeted_lc)

    # ── TDMS / CSV logging ───────────────────────────────────────────────

    def start_logging(self) -> Dict[str, Any]:
        if self.logging_enabled:
            return {"success": False, "message": "Already logging"}

        now = datetime.now()
        log_dir = Path("logs") / now.strftime("%m%d")
        log_dir.mkdir(parents=True, exist_ok=True)
        time_str = now.strftime("%H%M")

        with self._log_lock:
            self._log_dir = log_dir
            self._log_start_time = time.time()
            self._tdms_paths.clear()
            self._tdms_active.clear()

            for reader in self._readers:
                dtype = reader.device.device_info['device_type']
                safe = dtype.replace(' ', '_').replace('(', '').replace(')', '')
                path = log_dir / f"{time_str}_{safe}.tdms"
                ctr = 1
                while path.exists():
                    path = log_dir / f"{time_str}_{safe}_{ctr}.tdms"
                    ctr += 1

                try:
                    reader._task.in_stream.configure_logging(
                        str(path),
                        logging_mode=LoggingMode.LOG_AND_READ,
                        operation=LoggingOperation.CREATE_OR_REPLACE,
                        group_name=safe,
                    )
                    self._tdms_paths[dtype] = path
                    self._tdms_active[dtype] = True
                    logger.info(f"TDMS logging started: {path}")
                except Exception as e:
                    logger.error(
                        f"TDMS configure_logging failed for {dtype}: {e}\n"
                        "Check that nidaqmx supports configure_logging on this driver version."
                    )

            # TC CSV
            if self._tc_device:
                tc_path = log_dir / f"{time_str}_TC.csv"
                try:
                    self._tc_csv_file = open(tc_path, 'w', newline='')
                    self._tc_csv_writer = csv.writer(self._tc_csv_file)
                    hdr = (['timestamp', 'elapsed_ms']
                           + [f'TC{i}_degF' for i in range(self._tc_device.channel_count)])
                    self._tc_csv_writer.writerow(hdr)
                    self._tc_csv_rows = 0
                except Exception as e:
                    logger.error(f"TC CSV init failed: {e}")

            self.logging_enabled = True

        self._write_status_file()
        return {
            "success": True,
            "message": "Logging started",
            "tdms": {k: str(v) for k, v in self._tdms_paths.items()},
        }

    def stop_logging(self) -> Dict[str, Any]:
        if not self.logging_enabled:
            return {"success": False, "message": "Not logging"}

        with self._log_lock:
            self.logging_enabled = False

            # Stopping TDMS: the NI-DAQmx driver finalises the file when the
            # task is stopped or when configure_logging is called again with a
            # new path.  We mark it inactive here; the file is valid as written.
            self._tdms_active.clear()

            if self._tc_csv_file:
                try:
                    self._tc_csv_file.flush()
                    self._tc_csv_file.close()
                except Exception:
                    pass
                self._tc_csv_file = None
                self._tc_csv_writer = None

        logger.info(
            f"Logging stopped. TDMS files: "
            + ", ".join(str(p) for p in self._tdms_paths.values())
        )
        self._write_status_file(active=False)
        return {"success": True, "message": "Logging stopped"}

    def _write_tc_csv(self, processed: Dict[str, Any]) -> None:
        if not self._tc_csv_writer:
            return
        try:
            with self._log_lock:
                if not self._tc_csv_writer:
                    return
                ts = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                elapsed_ms = (
                    int((time.time() - self._log_start_time) * 1000)
                    if self._log_start_time else 0
                )
                channels = processed.get('channels', [])
                row = [ts, elapsed_ms] + [ch.get('temp_f', '') for ch in channels]
                self._tc_csv_writer.writerow(row)
                self._tc_csv_rows += 1
                if self._tc_csv_rows % 10 == 0 and self._tc_csv_file:
                    self._tc_csv_file.flush()
        except Exception as e:
            logger.warning(f"TC CSV write error: {e}")

    # ── Status file ──────────────────────────────────────────────────────

    def _write_status_file(self, active: Optional[bool] = None) -> None:
        try:
            is_active = active if active is not None else self.logging_enabled
            data = {
                "active": is_active,
                "tdms_files": {k: str(v) for k, v in self._tdms_paths.items()},
                "elapsed_sec": (
                    (time.time() - self._log_start_time)
                    if (is_active and self._log_start_time) else 0
                ),
                "updated_at": datetime.now().isoformat(),
            }
            with open(self._status_file, 'w') as f:
                json.dump(data, f)
        except Exception:
            pass

    # ── Node TCP ─────────────────────────────────────────────────────────

    def _ensure_node_socket(self) -> Optional[socket.socket]:
        with self._socket_lock:
            if self._node_socket is not None:
                return self._node_socket
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2.0)
                s.connect((self.node_host, self.node_port))
                s.settimeout(None)
                self._node_socket = s
                logger.info(f"Connected to Node at {self.node_host}:{self.node_port}")
            except Exception as e:
                logger.warning(f"Cannot reach Node ({self.node_host}:{self.node_port}): {e}")
                return None
            return self._node_socket

    def _close_node_socket(self) -> None:
        with self._socket_lock:
            if self._node_socket:
                try:
                    self._node_socket.close()
                except Exception:
                    pass
                self._node_socket = None

    def send_to_node_sync(self, data: Dict[str, Any]) -> None:
        payload = (json.dumps(data) + '\n').encode('utf-8')
        sock = self._ensure_node_socket()
        if sock is None:
            return
        try:
            sock.sendall(payload)
        except (BlockingIOError, InterruptedError):
            pass  # Drop frame — keep acquisition real-time
        except Exception:
            self._close_node_socket()  # Force reconnect on next call

    # ── Logging status API (called by Node via TCP message handler) ───────

    def get_logging_status(self) -> Dict[str, Any]:
        return {
            "active": self.logging_enabled,
            "tdms_files": {k: str(v) for k, v in self._tdms_paths.items()},
            "elapsed_sec": (
                (time.time() - self._log_start_time)
                if (self.logging_enabled and self._log_start_time) else 0
            ),
        }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

streamer_instance: Optional[DAQStreamer] = None


def main() -> None:
    global streamer_instance
    streamer_instance = DAQStreamer()
    try:
        streamer_instance.run()
    except KeyboardInterrupt:
        logger.info("Interrupted")
    finally:
        if streamer_instance:
            streamer_instance.stop()


if __name__ == '__main__':
    main()
