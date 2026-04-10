<script>
  import { pidGrid, pidConfig } from '../stores/pid.js';
  import { devices } from '../stores/devices.js';
  import { sendCommand } from '../stores/websocket.js';
  import { showToast } from '../stores/ui.js';
  import { formatValue } from '../utils/format.js';

  const CELL = 72;
  const HALF = CELL / 2;
  const PIPE_W = 4;

  $: grid = $pidGrid || [];
  $: config = $pidConfig || {};
  $: rows = grid.length;
  $: cols = grid[0]?.length || 0;
  $: svgW = cols * CELL;
  $: svgH = rows * CELL;

  // ── Fluid colors ──────────────────────────────────────────────────
  const FLUID_COLORS = {
    lox:   '#3182ce',
    fuel:  '#ed8936',
    gn2:   '#38a169',
    purge: '#9f7aea',
  };
  const DEFAULT_PIPE = '#718096';

  function fc(cell) {
    return FLUID_COLORS[cell?.fluid] || DEFAULT_PIPE;
  }

  // Get the color to use for a pipe stub going toward a neighbor.
  // Prefer our fluid, fall back to neighbor's fluid, then default.
  function stubColor(cell, neighborRow, neighborCol) {
    if (cell.fluid) return FLUID_COLORS[cell.fluid] || DEFAULT_PIPE;
    const n = grid[neighborRow]?.[neighborCol];
    if (n?.fluid) return FLUID_COLORS[n.fluid] || DEFAULT_PIPE;
    return DEFAULT_PIPE;
  }

  // ── Live data lookup ──────────────────────────────────────────────
  function getSensorValue(elemId) {
    const map = config[elemId?.toUpperCase()];
    if (!map) return null;
    const dev = $devices[map.device];
    if (!dev || !dev[map.type]) return null;
    const ch = dev[map.type][map.channel];
    return ch?.value ?? null;
  }

  function getSensorUnits(elemId) {
    const map = config[elemId?.toUpperCase()];
    return map?.units || 'psi';
  }

  function getSensorName(elemId) {
    const map = config[elemId?.toUpperCase()];
    return map?.name || elemId;
  }

  function getValveState(elemId) {
    const map = config[elemId?.toUpperCase()];
    if (!map) return null;
    const dev = $devices[map.device];
    if (!dev || !dev.dc) return null;
    return dev.dc[map.channel]?.state ?? false;
  }

  function toggleValve(elemId) {
    const map = config[elemId?.toUpperCase()];
    if (!map) return;
    const dev = $devices[map.device];
    if (!dev?.armed) {
      showToast('Not Armed', 'Arm the system before actuating valves', 'warning');
      return;
    }
    const current = getValveState(elemId);
    const next = current ? 0 : 1;
    sendCommand({
      action: 'send',
      device: map.device,
      command: `s${map.channel}${next}.00000`
    });
    showToast(elemId, next ? 'OPENED' : 'CLOSED', next ? 'success' : 'warning');
  }

  // ── Zoom/pan state ────────────────────────────────────────────────
  let scale = 1;
  let panX = 0;
  let panY = 0;
  let isPanning = false;
  let panStart = { x: 0, y: 0 };

  function onWheel(e) {
    e.preventDefault();
    scale = Math.max(0.3, Math.min(3, scale * (e.deltaY > 0 ? 0.9 : 1.1)));
  }

  function onMouseDown(e) {
    if (e.button === 1 || (e.button === 0 && e.shiftKey)) {
      isPanning = true;
      panStart = { x: e.clientX - panX, y: e.clientY - panY };
      e.preventDefault();
    }
  }
  function onMouseMove(e) {
    if (isPanning) {
      panX = e.clientX - panStart.x;
      panY = e.clientY - panStart.y;
    }
  }
  function onMouseUp() { isPanning = false; }
  function resetView() { scale = 1; panX = 0; panY = 0; }
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  class="pid-grid-container"
  on:wheel={onWheel}
  on:mousedown={onMouseDown}
  on:mousemove={onMouseMove}
  on:mouseup={onMouseUp}
  on:mouseleave={onMouseUp}
>
  {#if rows === 0}
    <div class="empty-state">
      <i class="fas fa-file-excel"></i>
      <h2>Load an XLSX P&ID Layout</h2>
      <p>Drag & drop an .xlsx file or use the file picker below.</p>
      <p class="hint">Each cell in the spreadsheet maps to a tile in the diagram.</p>
    </div>
  {:else}
    <div class="zoom-controls">
      <button on:click={() => scale = Math.min(3, scale * 1.2)} title="Zoom in">
        <i class="fas fa-search-plus"></i>
      </button>
      <button on:click={() => scale = Math.max(0.3, scale * 0.8)} title="Zoom out">
        <i class="fas fa-search-minus"></i>
      </button>
      <button on:click={resetView} title="Reset view">
        <i class="fas fa-compress-arrows-alt"></i>
      </button>
      <span class="zoom-level">{Math.round(scale * 100)}%</span>
    </div>

    <svg
      width={svgW}
      height={svgH}
      viewBox="0 0 {svgW} {svgH}"
      class="pid-svg"
      style="transform: scale({scale}) translate({panX / scale}px, {panY / scale}px);"
    >
      <defs>
        <pattern id="gridPattern" width={CELL} height={CELL} patternUnits="userSpaceOnUse">
          <rect width={CELL} height={CELL} fill="none" stroke="#f0f0f0" stroke-width="0.5" />
        </pattern>
      </defs>
      <rect width={svgW} height={svgH} fill="url(#gridPattern)" />

      {#each grid as row, r}
        {#each row as cell, c}
          {@const x = c * CELL}
          {@const y = r * CELL}
          {@const color = fc(cell)}
          {@const conn = cell.connections || {}}

          <g transform="translate({x}, {y})">

            {#if cell.type === 'pipe'}
              <!--
                For | and - pipes, draw the main axis line edge-to-edge.
                Also draw stubs toward any connected cross-axis neighbors
                so sensors/valves next to a pipe get a connecting line.
              -->
              {#if cell.dir === 'v'}
                <line x1={HALF} y1={0} x2={HALF} y2={CELL} stroke={color} stroke-width={PIPE_W} />
                {#if conn.left}
                  <line x1={0} y1={HALF} x2={HALF} y2={HALF} stroke={stubColor(cell, r, c-1)} stroke-width={PIPE_W} />
                {/if}
                {#if conn.right}
                  <line x1={HALF} y1={HALF} x2={CELL} y2={HALF} stroke={stubColor(cell, r, c+1)} stroke-width={PIPE_W} />
                {/if}
              {:else if cell.dir === 'h'}
                <line x1={0} y1={HALF} x2={CELL} y2={HALF} stroke={color} stroke-width={PIPE_W} />
                {#if conn.top}
                  <line x1={HALF} y1={0} x2={HALF} y2={HALF} stroke={stubColor(cell, r-1, c)} stroke-width={PIPE_W} />
                {/if}
                {#if conn.bottom}
                  <line x1={HALF} y1={HALF} x2={HALF} y2={CELL} stroke={stubColor(cell, r+1, c)} stroke-width={PIPE_W} />
                {/if}
              {:else if cell.dir === 'cross'}
                {#if conn.top}
                  <line x1={HALF} y1={0} x2={HALF} y2={HALF} stroke={stubColor(cell, r-1, c)} stroke-width={PIPE_W} />
                {/if}
                {#if conn.bottom}
                  <line x1={HALF} y1={HALF} x2={HALF} y2={CELL} stroke={stubColor(cell, r+1, c)} stroke-width={PIPE_W} />
                {/if}
                {#if conn.left}
                  <line x1={0} y1={HALF} x2={HALF} y2={HALF} stroke={stubColor(cell, r, c-1)} stroke-width={PIPE_W} />
                {/if}
                {#if conn.right}
                  <line x1={HALF} y1={HALF} x2={CELL} y2={HALF} stroke={stubColor(cell, r, c+1)} stroke-width={PIPE_W} />
                {/if}
              {:else if cell.dir === 'vv'}
                <line x1={HALF - 8} y1={0} x2={HALF - 8} y2={CELL} stroke={color} stroke-width={3} />
                <line x1={HALF + 8} y1={0} x2={HALF + 8} y2={CELL} stroke={color} stroke-width={3} />
              {:else if cell.dir === 'hh'}
                <line x1={0} y1={HALF - 8} x2={CELL} y2={HALF - 8} stroke={color} stroke-width={3} />
                <line x1={0} y1={HALF + 8} x2={CELL} y2={HALF + 8} stroke={color} stroke-width={3} />
              {/if}

            {:else if cell.type === 'pipe_element'}
              {@const elem = cell.element}
              <!-- Main pipe axis -->
              {#if cell.pipeDir === 'v'}
                <line x1={HALF} y1={0} x2={HALF} y2={CELL} stroke={color} stroke-width={PIPE_W} />
                {#if conn.left}
                  <line x1={0} y1={HALF} x2={HALF} y2={HALF} stroke={color} stroke-width={PIPE_W} />
                {/if}
                {#if conn.right}
                  <line x1={HALF} y1={HALF} x2={CELL} y2={HALF} stroke={color} stroke-width={PIPE_W} />
                {/if}
              {:else}
                <line x1={0} y1={HALF} x2={CELL} y2={HALF} stroke={color} stroke-width={PIPE_W} />
                {#if conn.top}
                  <line x1={HALF} y1={0} x2={HALF} y2={HALF} stroke={color} stroke-width={PIPE_W} />
                {/if}
                {#if conn.bottom}
                  <line x1={HALF} y1={HALF} x2={HALF} y2={CELL} stroke={color} stroke-width={PIPE_W} />
                {/if}
              {/if}

              <!-- Attached element -->
              {#if elem.kind === 'sensor'}
                {@const val = getSensorValue(elem.id)}
                <line x1={HALF} y1={HALF} x2={CELL - 4} y2={HALF - 14} stroke={color} stroke-width={2} />
                <rect x={HALF - 4} y={HALF - 30} width={CELL - HALF + 6} height={24} rx={3}
                      fill="white" stroke={color} stroke-width={1.5} />
                <text x={HALF + (CELL - HALF) / 2} y={HALF - 21} text-anchor="middle"
                      font-size="7" font-weight="700" fill={color} font-family="var(--font-mono)">
                  {elem.id}
                </text>
                <text x={HALF + (CELL - HALF) / 2} y={HALF - 11} text-anchor="middle"
                      font-size="9" font-weight="800" fill="#1a202c" font-family="var(--font-mono)">
                  {val !== null ? formatValue(val, 0) : '--'}
                </text>
              {:else if elem.kind === 'valve'}
                {@const isOpen = getValveState(elem.id)}
                {@const vc = isOpen ? '#48bb78' : '#e53e3e'}
                <polygon points="{HALF - 10},{HALF - 10} {HALF},{HALF} {HALF - 10},{HALF + 10}" fill={vc} stroke={color} stroke-width={1} />
                <polygon points="{HALF + 10},{HALF - 10} {HALF},{HALF} {HALF + 10},{HALF + 10}" fill={vc} stroke={color} stroke-width={1} />
                <text x={HALF} y={HALF + 24} text-anchor="middle"
                      font-size="7" font-weight="700" fill="#1a202c" font-family="var(--font-sans)">
                  {elem.id}
                </text>
              {/if}

            {:else if cell.type === 'sensor'}
              {@const val = getSensorValue(cell.id)}
              <!-- Pipe stubs to ALL connected neighbors -->
              {#if conn.top}
                <line x1={HALF} y1={0} x2={HALF} y2={HALF - 18} stroke={stubColor(cell, r-1, c)} stroke-width={PIPE_W} />
              {/if}
              {#if conn.bottom}
                <line x1={HALF} y1={HALF + 18} x2={HALF} y2={CELL} stroke={stubColor(cell, r+1, c)} stroke-width={PIPE_W} />
              {/if}
              {#if conn.left}
                <line x1={0} y1={HALF} x2={HALF - 18} y2={HALF} stroke={stubColor(cell, r, c-1)} stroke-width={PIPE_W} />
              {/if}
              {#if conn.right}
                <line x1={HALF + 18} y1={HALF} x2={CELL} y2={HALF} stroke={stubColor(cell, r, c+1)} stroke-width={PIPE_W} />
              {/if}
              <!-- Sensor circle -->
              <circle cx={HALF} cy={HALF} r={18} fill="white" stroke={color} stroke-width={2} />
              <text x={HALF} y={HALF - 4} text-anchor="middle"
                    font-size="8" font-weight="700" fill={color} font-family="var(--font-mono)">
                {cell.id}
              </text>
              <text x={HALF} y={HALF + 8} text-anchor="middle"
                    font-size="10" font-weight="800" fill="#1a202c" font-family="var(--font-mono)">
                {val !== null ? formatValue(val, 0) : '--'}
              </text>

            {:else if cell.type === 'valve'}
              {@const isOpen = getValveState(cell.id)}
              {@const stateColor = isOpen === true ? '#48bb78' : isOpen === false ? '#e53e3e' : '#94a3b8'}
              <!-- Pipe stubs to ALL connected neighbors -->
              {#if conn.top}
                <line x1={HALF} y1={0} x2={HALF} y2={HALF - 14} stroke={stubColor(cell, r-1, c)} stroke-width={PIPE_W} />
              {/if}
              {#if conn.bottom}
                <line x1={HALF} y1={HALF + 14} x2={HALF} y2={CELL} stroke={stubColor(cell, r+1, c)} stroke-width={PIPE_W} />
              {/if}
              {#if conn.left}
                <line x1={0} y1={HALF} x2={HALF - 14} y2={HALF} stroke={stubColor(cell, r, c-1)} stroke-width={PIPE_W} />
              {/if}
              {#if conn.right}
                <line x1={HALF + 14} y1={HALF} x2={CELL} y2={HALF} stroke={stubColor(cell, r, c+1)} stroke-width={PIPE_W} />
              {/if}
              <!-- Valve bowtie -->
              <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-noninteractive-element-interactions -->
              <polygon points="{HALF - 14},{HALF - 14} {HALF},{HALF} {HALF - 14},{HALF + 14}"
                       fill={stateColor} stroke={color} stroke-width={1.5}
                       on:click={() => toggleValve(cell.id)}
                       role="button" class="valve-shape" />
              <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-noninteractive-element-interactions -->
              <polygon points="{HALF + 14},{HALF - 14} {HALF},{HALF} {HALF + 14},{HALF + 14}"
                       fill={stateColor} stroke={color} stroke-width={1.5}
                       on:click={() => toggleValve(cell.id)}
                       role="button" class="valve-shape" />
              <text x={HALF} y={HALF + 28} text-anchor="middle"
                    font-size="8" font-weight="700" fill="#1a202c" font-family="var(--font-sans)">
                {cell.id}
              </text>
              <text x={HALF} y={HALF - 20} text-anchor="middle"
                    font-size="7" font-weight="600"
                    fill={isOpen ? '#38a169' : '#e53e3e'} font-family="var(--font-sans)">
                {isOpen === true ? 'OPEN' : isOpen === false ? 'SHUT' : ''}
              </text>

            {:else if cell.type === 'engine'}
              <!-- Pipe stubs -->
              {#if conn.top}
                <line x1={HALF} y1={0} x2={HALF} y2={10} stroke={stubColor(cell, r-1, c)} stroke-width={PIPE_W} />
              {/if}
              {#if conn.left}
                <line x1={0} y1={HALF} x2={12} y2={HALF} stroke={stubColor(cell, r, c-1)} stroke-width={PIPE_W} />
              {/if}
              {#if conn.right}
                <line x1={CELL - 12} y1={HALF} x2={CELL} y2={HALF} stroke={stubColor(cell, r, c+1)} stroke-width={PIPE_W} />
              {/if}
              <!-- Engine triangle -->
              <polygon points="{HALF},{8} {8},{CELL - 4} {CELL - 8},{CELL - 4}"
                       fill="none" stroke="#e53e3e" stroke-width={2.5} stroke-linejoin="round" />
              <text x={HALF} y={HALF + 6} text-anchor="middle"
                    font-size="9" font-weight="800" fill="#e53e3e" font-family="var(--font-sans)">
                ENGINE
              </text>

            {:else if cell.type === 'tank'}
              {@const tf = cell.tankFluid || cell.fluid || 'lox'}
              {@const tc = FLUID_COLORS[tf] || DEFAULT_PIPE}
              <!-- Pipe stubs -->
              {#if conn.top}
                <line x1={HALF} y1={0} x2={HALF} y2={4} stroke={tc} stroke-width={PIPE_W} />
              {/if}
              {#if conn.bottom}
                <line x1={HALF} y1={CELL - 4} x2={HALF} y2={CELL} stroke={tc} stroke-width={PIPE_W} />
              {/if}
              {#if conn.left}
                <line x1={0} y1={HALF} x2={4} y2={HALF} stroke={tc} stroke-width={PIPE_W} />
              {/if}
              {#if conn.right}
                <line x1={CELL - 4} y1={HALF} x2={CELL} y2={HALF} stroke={tc} stroke-width={PIPE_W} />
              {/if}
              <!-- Tank body -->
              <rect x={4} y={4} width={CELL - 8} height={CELL - 8} rx={8}
                    fill="{tc}18" stroke={tc} stroke-width={2} />
              <text x={HALF} y={HALF + 3} text-anchor="middle"
                    font-size="8" font-weight="800" fill={tc} font-family="var(--font-sans)">
                {cell.label || 'TANK'}
              </text>

            {:else if cell.type === 'supply'}
              <!-- Pipe stubs -->
              {#if conn.top}
                <line x1={HALF} y1={0} x2={HALF} y2={6} stroke="#38a169" stroke-width={PIPE_W} />
              {/if}
              {#if conn.bottom}
                <line x1={HALF} y1={CELL - 6} x2={HALF} y2={CELL} stroke="#38a169" stroke-width={PIPE_W} />
              {/if}
              {#if conn.left}
                <line x1={0} y1={HALF} x2={6} y2={HALF} stroke="#38a169" stroke-width={PIPE_W} />
              {/if}
              {#if conn.right}
                <line x1={CELL - 6} y1={HALF} x2={CELL} y2={HALF} stroke="#38a169" stroke-width={PIPE_W} />
              {/if}
              <polygon points="{HALF},{6} {CELL - 6},{HALF} {HALF},{CELL - 6} {6},{HALF}"
                       fill="#38a16918" stroke="#38a169" stroke-width={2} />
              <text x={HALF} y={HALF + 4} text-anchor="middle"
                    font-size="9" font-weight="800" fill="#38a169" font-family="var(--font-sans)">
                {cell.label || 'GN2'}
              </text>

            {:else if cell.type === 'label'}
              <text x={HALF} y={HALF + 4} text-anchor="middle"
                    font-size="9" font-weight="600" fill="#4a5568" font-family="var(--font-sans)">
                {cell.label}
              </text>
            {/if}
          </g>
        {/each}
      {/each}
    </svg>
  {/if}
</div>

<style>
  .pid-grid-container {
    flex: 1;
    overflow: auto;
    background: var(--bg-surface);
    display: flex;
    align-items: flex-start;
    justify-content: flex-start;
    position: relative;
    cursor: default;
  }
  .pid-svg {
    transform-origin: 0 0;
    transition: transform 0.1s ease;
    cursor: grab;
    margin: 20px;
  }
  .pid-svg:active { cursor: grabbing; }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    gap: 12px;
    color: var(--text-tertiary);
  }
  .empty-state i { font-size: 64px; color: var(--green-400); opacity: 0.5; }
  .empty-state h2 { font-size: 20px; font-weight: 700; color: var(--text-secondary); }
  .empty-state p { font-size: 14px; color: var(--text-tertiary); }
  .empty-state .hint { font-size: 12px; color: var(--text-muted); font-style: italic; }

  .zoom-controls {
    position: absolute;
    top: 12px;
    right: 12px;
    display: flex;
    gap: 4px;
    align-items: center;
    z-index: 20;
    background: var(--bg-surface);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-md);
    padding: 4px;
    box-shadow: var(--shadow-sm);
  }
  .zoom-controls button {
    width: 28px; height: 28px;
    border: none; background: transparent;
    border-radius: var(--radius-sm); cursor: pointer;
    color: var(--text-secondary); font-size: 12px;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.15s;
  }
  .zoom-controls button:hover { background: var(--bg-elevated); color: var(--text-primary); }
  .zoom-level {
    font-size: 10px; font-weight: 600;
    color: var(--text-tertiary); padding: 0 6px;
    font-family: var(--font-mono);
  }

  :global(.valve-shape) { cursor: pointer; transition: opacity 0.15s; }
  :global(.valve-shape:hover) { opacity: 0.8; }
</style>
