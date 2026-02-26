#!/usr/bin/env python3
"""
Read sensor_config.xlsx and regenerate all JSON config files used by HTML UIs.
Run before starting either system, or called automatically at startup.
"""

import json
import os
import sys

def _xlsx_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sensor_config.xlsx')


def load_xlsx():
    import openpyxl
    path = _xlsx_path()
    if not os.path.exists(path):
        print(f"[generate_configs] sensor_config.xlsx not found at {path}")
        return None
    return openpyxl.load_workbook(path, read_only=True, data_only=True)


def _read_sheet(wb, sheet_name):
    """Read a sheet and return (headers, rows) where each row is a dict."""
    ws = wb[sheet_name]
    headers = [cell for cell in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
    col = {h: i for i, h in enumerate(headers) if h}
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        d = {}
        for h, i in col.items():
            d[h] = row[i]
        rows.append(d)
    return rows


def _safe(val, default=''):
    """Return val as string, or default if None."""
    return str(val) if val is not None else default


def _safef(val, default=0.0):
    """Return val as float, or default if None."""
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def _safei(val, default=0):
    try:
        return int(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def generate_panda_pt(rows):
    """Generate panda/configs/pt_channels.json"""
    channels = []
    for r in rows:
        if _safe(r.get('system')).strip().lower() != 'panda':
            continue
        ch = _safei(r.get('channel'))
        channels.append({
            "pt": {
                "id": ch + 1,
                "raw_index": ch + 1,
                "name": _safe(r.get('name'), f'PT{ch + 1}').upper(),
                "short_name": _safe(r.get('short_name'), f'pt{ch + 1}'),
                "units": _safe(r.get('units'), 'psi'),
                "range": [0, 500],
            }
        })
    return {"channels": channels}


def generate_panda_lc(rows):
    """Generate panda/configs/lc_channels.json"""
    channels = []
    for r in rows:
        if _safe(r.get('system')).strip().lower() != 'panda':
            continue
        ch = _safei(r.get('channel'))
        channels.append({
            "lc": {
                "id": ch + 1,
                "raw_index": ch + 1,
                "name": _safe(r.get('name'), f'LC{ch + 1}'),
                "short_name": _safe(r.get('short_name'), f'lc{ch + 1}'),
                "units": _safe(r.get('units'), 'lbf'),
                "range": [0, 1000],
                "calibration": {
                    "slope": _safef(r.get('cal_slope_a'), 1000000.0),
                    "slope_alt": _safef(r.get('cal_slope_b'), 1000000.0),
                    "slope_alt_label": "Cal B",
                    "offset": _safef(r.get('cal_offset'), 0.0),
                    "tare_offset": _safef(r.get('cal_tare'), 0.0),
                }
            }
        })
    return {"channels": channels}


def generate_panda_tc(rows):
    """Generate panda/configs/tc_channels.json"""
    channels = []
    for r in rows:
        if _safe(r.get('system')).strip().lower() != 'panda':
            continue
        ch = _safei(r.get('channel'))
        channels.append({
            "tc": {
                "id": ch + 1,
                "raw_index": ch + 1,
                "name": _safe(r.get('name'), f'TC{ch + 1}'),
                "short_name": _safe(r.get('short_name'), f'tc{ch + 1}'),
                "tc_type": _safe(r.get('tc_type'), 'K').upper(),
                "units": _safe(r.get('units'), '°C'),
                "range": [
                    _safef(r.get('cal_min_temp'), 0),
                    _safef(r.get('cal_max_temp'), 2000),
                ] if r.get('cal_min_temp') is not None else [0, 2000],
                "calibration": {
                    "offset": _safef(r.get('tc_cal_offset'), 0.0),
                    "min_temp": _safef(r.get('cal_min_temp'), -320.0) if r.get('cal_min_temp') is not None else -320.0,
                    "max_temp": _safef(r.get('cal_max_temp'), 2282.0) if r.get('cal_max_temp') is not None else 2282.0,
                }
            }
        })
    return {"channels": channels}


def generate_panda_dc(rows):
    """Generate panda/configs/dc_channels.json"""
    channels = []
    for r in rows:
        if _safe(r.get('system')).strip().lower() != 'panda':
            continue
        ch = _safei(r.get('channel'))
        entry = {
            "id": ch + 1,
            "raw_index": ch + 1,
            "name": _safe(r.get('name'), f'DC{ch + 1}'),
            "short_name": _safe(r.get('short_name'), f'dc{ch + 1}'),
            "type": _safe(r.get('dc_type'), 'misc'),
        }
        abort_role = r.get('abort_role')
        if abort_role:
            entry["abort_role"] = str(abort_role)
        bb = r.get('bb_enabled')
        if bb and str(bb).strip().upper() == 'TRUE':
            entry["bb"] = True
        channels.append({"dc": entry})
    return {"channels": channels}


def generate_nidaq_interface_config(pt_rows):
    """Regenerate the sensors section of ni_daq/interface_config.json"""
    base = os.path.dirname(os.path.abspath(__file__))
    iface_path = os.path.join(base, 'ni_daq', 'interface_config.json')

    # Preserve existing non-sensor sections
    existing = {}
    if os.path.exists(iface_path):
        try:
            with open(iface_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except Exception:
            pass

    sensors = []
    for r in pt_rows:
        if _safe(r.get('system')).strip().lower() != 'ni_daq':
            continue
        ch = _safei(r.get('channel'))
        sensor = {
            "channel": ch,
            "name": _safe(r.get('name'), f'PT{ch}'),
            "id": _safe(r.get('id'), f'PT{ch}E'),
            "group": _safe(r.get('group'), 'other'),
            "calibration": {
                "max_psi": _safef(r.get('cal_max_psi_a'), 10000.0),
                "zero_ma": _safef(r.get('cal_zero_ma'), 4.0),
                "units": _safe(r.get('units'), 'psi'),
            }
        }
        serial = r.get('serial')
        if serial:
            sensor["serial"] = str(serial)
        sensors.append(sensor)

    existing["sensors"] = sensors
    # Keep interface/blowdown sections if present, add defaults if not
    if "interface" not in existing:
        existing["interface"] = {
            "title": "ERPL DAQ Monitor",
            "layout": {"pid_width_percent": 50, "data_width_percent": 50},
            "theme": {"mode": "light", "high_contrast": True}
        }

    return existing, iface_path


def generate_nidaq_lc_channels(lc_rows):
    """Generate ni_daq/lc_channels.json"""
    channels = []
    for r in lc_rows:
        if _safe(r.get('system')).strip().lower() != 'ni_daq':
            continue
        ch = _safei(r.get('channel'))
        channels.append({
            "lc": {
                "id": ch + 1,
                "name": _safe(r.get('name'), f'LC{ch + 1}'),
                "short_name": _safe(r.get('short_name'), f'lc{ch + 1}'),
                "units": _safe(r.get('units'), 'lbf'),
                "range": [-100, 100],
                "calibration": {
                    "slope": _safef(r.get('cal_slope_a'), 1000000.0),
                    "slope_alt": _safef(r.get('cal_slope_b'), 1000000.0),
                    "slope_alt_label": "Cal B",
                    "offset": _safef(r.get('cal_offset'), 0.0),
                    "tare_offset": _safef(r.get('cal_tare'), 0.0),
                }
            }
        })
    return {"channels": channels}


def generate_nidaq_tc_channels(tc_rows):
    """Generate ni_daq/tc_channels.json"""
    channels = []
    for r in tc_rows:
        if _safe(r.get('system')).strip().lower() != 'ni_daq':
            continue
        ch = _safei(r.get('channel'))
        channels.append({
            "tc": {
                "id": ch + 1,
                "name": _safe(r.get('name'), f'TC{ch + 1}'),
                "short_name": _safe(r.get('short_name'), f'tc{ch + 1}'),
                "tc_type": _safe(r.get('tc_type'), 'K').upper(),
                "units": _safe(r.get('units'), '°F'),
                "range": [
                    _safef(r.get('cal_min_temp'), -320),
                    _safef(r.get('cal_max_temp'), 200),
                ],
                "calibration": {
                    "offset": _safef(r.get('tc_cal_offset'), 0.0),
                    "min_temp": _safef(r.get('cal_min_temp'), -320.0),
                    "max_temp": _safef(r.get('cal_max_temp'), 2282.0),
                }
            }
        })
    return {"channels": channels}


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"  -> {path}")


def run():
    wb = load_xlsx()
    if wb is None:
        return False

    base = os.path.dirname(os.path.abspath(__file__))

    pt_rows = _read_sheet(wb, 'PT_Sensors')
    lc_rows = _read_sheet(wb, 'LC_LoadCells')
    tc_rows = _read_sheet(wb, 'TC_Thermocouples')
    dc_rows = _read_sheet(wb, 'DC_Solenoids')
    wb.close()

    print("[generate_configs] Regenerating JSON configs from sensor_config.xlsx ...")

    # Panda configs
    _write_json(os.path.join(base, 'panda', 'configs', 'pt_channels.json'), generate_panda_pt(pt_rows))
    _write_json(os.path.join(base, 'panda', 'configs', 'lc_channels.json'), generate_panda_lc(lc_rows))
    _write_json(os.path.join(base, 'panda', 'configs', 'tc_channels.json'), generate_panda_tc(tc_rows))
    _write_json(os.path.join(base, 'panda', 'configs', 'dc_channels.json'), generate_panda_dc(dc_rows))

    # NI DAQ configs
    iface_data, iface_path = generate_nidaq_interface_config(pt_rows)
    _write_json(iface_path, iface_data)
    _write_json(os.path.join(base, 'ni_daq', 'lc_channels.json'), generate_nidaq_lc_channels(lc_rows))
    _write_json(os.path.join(base, 'ni_daq', 'tc_channels.json'), generate_nidaq_tc_channels(tc_rows))

    print("[generate_configs] Done.")
    return True


if __name__ == '__main__':
    success = run()
    sys.exit(0 if success else 1)
