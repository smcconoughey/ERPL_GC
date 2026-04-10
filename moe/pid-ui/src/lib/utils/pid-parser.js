import { read, utils } from 'xlsx';

// ── Cell type patterns ──────────────────────────────────────────────
const SENSOR_RE = /^(PT|TC|LC|PI|PV)(\d+)$/i;
const VALVE_RE  = /^(PB|SV|S)(\d+)$/i;
const PIPE_ELEMENT_RE = /^([|\-]),\s*(.+)$/;
const TANK_RE   = /^(LOX|FUEL|GN2|N2O)[\s_]?TANK$/i;
const ENGINE_RE = /^ENGINE$/i;
const SUPPLY_RE = /^(GN2|N2|HE|PRESS)$/i;

// ── Fill color to fluid mapping ─────────────────────────────────────
const COLOR_MAP = {
  '3182CE': 'lox',    'FF3182CE': 'lox',
  '4472C4': 'lox',    'FF4472C4': 'lox',
  '5B9BD5': 'lox',    'FF5B9BD5': 'lox',
  '0070C0': 'lox',    'FF0070C0': 'lox',
  'ED8936': 'fuel',   'FFED8936': 'fuel',
  'F4B084': 'fuel',   'FFF4B084': 'fuel',
  'ED7D31': 'fuel',   'FFED7D31': 'fuel',
  'FFC000': 'fuel',   'FFFFC000': 'fuel',
  '38A169': 'gn2',    'FF38A169': 'gn2',
  '70AD47': 'gn2',    'FF70AD47': 'gn2',
  '00B050': 'gn2',    'FF00B050': 'gn2',
  'A9D18E': 'gn2',    'FFA9D18E': 'gn2',
  '9F7AEA': 'purge',  'FF9F7AEA': 'purge',
  '7030A0': 'purge',  'FF7030A0': 'purge',
  'B4A7D6': 'purge',  'FFB4A7D6': 'purge',
};

function colorToFluid(fillObj) {
  if (!fillObj) return null;
  if (fillObj.rgb) return COLOR_MAP[fillObj.rgb] || null;
  return null;
}

// ── Parse a single cell ─────────────────────────────────────────────
function parseCell(raw, fluid) {
  if (!raw) return { type: 'empty', raw: '', fluid: null };

  // Pipe + element combo: "|,PT5" or "-,PB3"
  const combo = raw.match(PIPE_ELEMENT_RE);
  if (combo) {
    const pipeDir = combo[1] === '|' ? 'v' : 'h';
    const elemRaw = combo[2].trim();
    return {
      type: 'pipe_element',
      pipeDir,
      element: classifyElement(elemRaw),
      fluid,
      raw,
    };
  }

  // Pipe characters
  if (raw === '|')  return { type: 'pipe', dir: 'v',     fluid, raw };
  if (raw === '-')  return { type: 'pipe', dir: 'h',     fluid, raw };
  if (raw === '+')  return { type: 'pipe', dir: 'cross', fluid, raw };
  if (raw === '||') return { type: 'pipe', dir: 'vv',    fluid, raw };
  if (raw === '--') return { type: 'pipe', dir: 'hh',    fluid, raw };

  // Standalone elements
  const elem = classifyElement(raw);
  if (elem.kind !== 'label') {
    return { type: elem.kind, ...elem, fluid, raw };
  }

  // Fallback: treat as text label
  return { type: 'label', label: raw, fluid, raw };
}

function classifyElement(text) {
  const t = text.trim();
  const upper = t.toUpperCase();

  if (SENSOR_RE.test(upper)) {
    const m = upper.match(SENSOR_RE);
    return { kind: 'sensor', id: upper, sensorType: m[1], num: parseInt(m[2]) };
  }
  if (VALVE_RE.test(upper)) {
    const m = upper.match(VALVE_RE);
    return { kind: 'valve', id: upper, valveType: m[1], num: parseInt(m[2]) };
  }
  if (ENGINE_RE.test(upper)) {
    return { kind: 'engine', id: 'ENGINE', label: 'Engine' };
  }
  if (TANK_RE.test(upper)) {
    const fluidGuess = upper.startsWith('LOX') ? 'lox'
                     : upper.startsWith('FUEL') ? 'fuel'
                     : upper.startsWith('N2O') ? 'fuel'
                     : 'gn2';
    return { kind: 'tank', id: upper.replace(/\s+/g, '_'), label: t, tankFluid: fluidGuess };
  }
  if (SUPPLY_RE.test(upper)) {
    return { kind: 'supply', id: upper, label: upper };
  }

  return { kind: 'label', id: null, label: t };
}

// ── Is this cell something pipes can connect to? ────────────────────
function isConnectable(cell) {
  return cell.type !== 'empty' && cell.type !== 'label';
}

// ── What directions does this cell OFFER connections? ────────────────
// Pipes only offer along their axis; everything else offers all 4.
function offeredDirs(cell) {
  if (cell.type === 'pipe') {
    switch (cell.dir) {
      case 'v':  return { top: true,  bottom: true,  left: false, right: false };
      case 'h':  return { top: false, bottom: false, left: true,  right: true  };
      case 'vv': return { top: true,  bottom: true,  left: false, right: false };
      case 'hh': return { top: false, bottom: false, left: true,  right: true  };
      case 'cross': return { top: true, bottom: true, left: true, right: true };
    }
  }
  if (cell.type === 'pipe_element') {
    // Main pipe direction is always connected, plus the element can branch
    if (cell.pipeDir === 'v') return { top: true, bottom: true, left: true, right: true };
    if (cell.pipeDir === 'h') return { top: true, bottom: true, left: true, right: true };
  }
  // Sensors, valves, tanks, engine, supply: accept from any direction
  if (isConnectable(cell)) {
    return { top: true, bottom: true, left: true, right: true };
  }
  return { top: false, bottom: false, left: false, right: false };
}

// ── Resolve connections between adjacent cells ──────────────────────
// Two cells connect if BOTH offer a connection toward each other.
function resolveConnections(grid) {
  const rows = grid.length;
  for (let r = 0; r < rows; r++) {
    const cols = grid[r].length;
    for (let c = 0; c < cols; c++) {
      const cell = grid[r][c];
      if (!isConnectable(cell)) continue;

      const mine = offeredDirs(cell);
      const top    = r > 0      ? grid[r-1][c] : null;
      const bottom = r < rows-1 ? grid[r+1][c] : null;
      const left   = c > 0      ? grid[r][c-1] : null;
      const right  = c < cols-1 ? grid[r][c+1] : null;

      cell.connections = {
        top:    mine.top    && top    && isConnectable(top)    && offeredDirs(top).bottom,
        bottom: mine.bottom && bottom && isConnectable(bottom) && offeredDirs(bottom).top,
        left:   mine.left   && left   && isConnectable(left)   && offeredDirs(left).right,
        right:  mine.right  && right  && isConnectable(right)  && offeredDirs(right).left,
      };
    }
  }
}

// ── Propagate fluid colors ──────────────────────────────────────────
// After connections are resolved, spread fluid types from cells that
// have an explicit fluid to their connected neighbors that don't.
function propagateFluids(grid) {
  const rows = grid.length;
  const cols = grid[0]?.length || 0;
  let changed = true;

  while (changed) {
    changed = false;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const cell = grid[r][c];
        if (!isConnectable(cell) || cell.fluid) continue;

        const conn = cell.connections;
        // Check neighbors for a fluid to inherit
        const neighbors = [];
        if (conn.top)    neighbors.push(grid[r-1][c]);
        if (conn.bottom) neighbors.push(grid[r+1][c]);
        if (conn.left)   neighbors.push(grid[r][c-1]);
        if (conn.right)  neighbors.push(grid[r][c+1]);

        for (const n of neighbors) {
          if (n.fluid) {
            cell.fluid = n.fluid;
            changed = true;
            break;
          }
        }
      }
    }
  }
}

// ── Main parse function ─────────────────────────────────────────────
export function parseXlsx(arrayBuffer) {
  const wb = read(arrayBuffer, { type: 'array', cellStyles: true });

  const pidSheetName = wb.SheetNames.find(n => {
    const up = n.toUpperCase();
    return up.includes('PID') || up.includes('P&ID') || up.includes('LAYOUT');
  }) || wb.SheetNames[0];

  const ws = wb.Sheets[pidSheetName];
  if (!ws['!ref']) return { grid: [], rows: 0, cols: 0 };

  const range = utils.decode_range(ws['!ref']);
  const rows = range.e.r + 1;
  const cols = range.e.c + 1;

  const grid = [];

  for (let r = 0; r <= range.e.r; r++) {
    const row = [];
    for (let c = 0; c <= range.e.c; c++) {
      const addr = utils.encode_cell({ r, c });
      const cell = ws[addr];
      const rawVal = cell ? String(cell.v ?? '').trim() : '';

      let fluid = null;
      if (cell && cell.s && cell.s.fgColor) {
        fluid = colorToFluid(cell.s.fgColor);
      }
      if (!fluid && cell && cell.s && cell.s.bgColor) {
        fluid = colorToFluid(cell.s.bgColor);
      }

      row.push(parseCell(rawVal, fluid));
    }
    grid.push(row);
  }

  resolveConnections(grid);
  propagateFluids(grid);

  return { grid, rows, cols, sheetName: pidSheetName };
}

export { classifyElement, offeredDirs, isConnectable };
