<script>
  const CELL = 52;
  const HALF = CELL / 2;

  const symbols = [
    { label: '|', desc: 'Vertical pipe', type: 'pipe_v' },
    { label: '-', desc: 'Horizontal pipe', type: 'pipe_h' },
    { label: '+', desc: 'Junction / corner (auto-connects to neighbors)', type: 'pipe_cross' },
    { label: '||', desc: 'Double vertical pipe', type: 'pipe_vv' },
    { label: '--', desc: 'Double horizontal pipe', type: 'pipe_hh' },
    { label: 'PT#', desc: 'Pressure transducer (shows live psi)', type: 'sensor' },
    { label: 'TC#', desc: 'Thermocouple (shows live temp)', type: 'sensor_tc' },
    { label: 'LC#', desc: 'Load cell (shows live force)', type: 'sensor_lc' },
    { label: 'PB#', desc: 'Ball valve (click to toggle when armed)', type: 'valve' },
    { label: 'SV#', desc: 'Solenoid valve', type: 'valve_sv' },
    { label: '|,PT5', desc: 'Pipe with sensor branch', type: 'pipe_sensor' },
    { label: '-,PB3', desc: 'Pipe with inline valve', type: 'pipe_valve' },
    { label: 'Engine', desc: 'Engine / combustion chamber (triangle)', type: 'engine' },
    { label: 'LOX_TANK', desc: 'LOX tank (blue)', type: 'tank_lox' },
    { label: 'FUEL_TANK', desc: 'Fuel tank (orange)', type: 'tank_fuel' },
    { label: 'GN2', desc: 'Pressurant supply (diamond)', type: 'supply' },
  ];

  const fluids = [
    { color: '#3182ce', name: 'LOX', desc: 'Blue cell fill in Excel' },
    { color: '#ed8936', name: 'Fuel', desc: 'Orange cell fill in Excel' },
    { color: '#38a169', name: 'GN2', desc: 'Green cell fill in Excel' },
    { color: '#9f7aea', name: 'Purge', desc: 'Purple cell fill in Excel' },
    { color: '#718096', name: 'Default', desc: 'No fill / unspecified' },
  ];
</script>

<div class="legend-view">
  <div class="legend-card">
    <h2>Cell Symbols</h2>
    <p class="legend-intro">
      Each cell in the XLSX spreadsheet becomes one tile in the P&ID diagram.
      Type these values into cells to build your layout.
    </p>

    <div class="symbols-grid">
      {#each symbols as sym}
        <div class="symbol-row">
          <div class="symbol-preview">
            <svg width={CELL} height={CELL} viewBox="0 0 {CELL} {CELL}">
              <rect width={CELL} height={CELL} fill="#f8fafc" stroke="#e2e8f0" rx="3" />
              {#if sym.type === 'pipe_v'}
                <line x1={HALF} y1={0} x2={HALF} y2={CELL} stroke="#718096" stroke-width={3} />
              {:else if sym.type === 'pipe_h'}
                <line x1={0} y1={HALF} x2={CELL} y2={HALF} stroke="#718096" stroke-width={3} />
              {:else if sym.type === 'pipe_cross'}
                <line x1={HALF} y1={0} x2={HALF} y2={CELL} stroke="#718096" stroke-width={3} />
                <line x1={0} y1={HALF} x2={CELL} y2={HALF} stroke="#718096" stroke-width={3} />
                <circle cx={HALF} cy={HALF} r={2.5} fill="#718096" />
              {:else if sym.type === 'pipe_vv'}
                <line x1={HALF - 6} y1={0} x2={HALF - 6} y2={CELL} stroke="#718096" stroke-width={2.5} />
                <line x1={HALF + 6} y1={0} x2={HALF + 6} y2={CELL} stroke="#718096" stroke-width={2.5} />
              {:else if sym.type === 'pipe_hh'}
                <line x1={0} y1={HALF - 6} x2={CELL} y2={HALF - 6} stroke="#718096" stroke-width={2.5} />
                <line x1={0} y1={HALF + 6} x2={CELL} y2={HALF + 6} stroke="#718096" stroke-width={2.5} />
              {:else if sym.type === 'sensor' || sym.type === 'sensor_tc' || sym.type === 'sensor_lc'}
                <circle cx={HALF} cy={HALF} r={12} fill="white" stroke="#3182ce" stroke-width={1.5} />
                <text x={HALF} y={HALF - 2} text-anchor="middle" font-size="6" font-weight="700" fill="#3182ce">{sym.label}</text>
                <text x={HALF} y={HALF + 7} text-anchor="middle" font-size="7" font-weight="800" fill="#1a202c">125</text>
              {:else if sym.type === 'valve' || sym.type === 'valve_sv'}
                <polygon points="{HALF - 10},{HALF - 10} {HALF},{HALF} {HALF - 10},{HALF + 10}" fill="#48bb78" stroke="#718096" />
                <polygon points="{HALF + 10},{HALF - 10} {HALF},{HALF} {HALF + 10},{HALF + 10}" fill="#48bb78" stroke="#718096" />
                <text x={HALF} y={HALF + 20} text-anchor="middle" font-size="6" font-weight="700" fill="#1a202c">{sym.label}</text>
              {:else if sym.type === 'pipe_sensor'}
                <line x1={HALF} y1={0} x2={HALF} y2={CELL} stroke="#718096" stroke-width={3} />
                <line x1={HALF} y1={HALF} x2={CELL - 4} y2={HALF - 8} stroke="#718096" stroke-width={1.5} />
                <circle cx={CELL - 6} cy={HALF - 10} r={6} fill="white" stroke="#3182ce" stroke-width={1} />
                <text x={CELL - 6} y={HALF - 8} text-anchor="middle" font-size="5" font-weight="700" fill="#3182ce">PT</text>
              {:else if sym.type === 'pipe_valve'}
                <line x1={0} y1={HALF} x2={CELL} y2={HALF} stroke="#718096" stroke-width={3} />
                <polygon points="{HALF - 8},{HALF - 8} {HALF},{HALF} {HALF - 8},{HALF + 8}" fill="#48bb78" stroke="#718096" />
                <polygon points="{HALF + 8},{HALF - 8} {HALF},{HALF} {HALF + 8},{HALF + 8}" fill="#48bb78" stroke="#718096" />
              {:else if sym.type === 'engine'}
                <polygon points="{HALF},{4} {4},{CELL - 4} {CELL - 4},{CELL - 4}" fill="none" stroke="#e53e3e" stroke-width={2} />
                <text x={HALF} y={HALF + 4} text-anchor="middle" font-size="6" font-weight="800" fill="#e53e3e">ENG</text>
              {:else if sym.type === 'tank_lox'}
                <rect x={3} y={3} width={CELL - 6} height={CELL - 6} rx={6} fill="#3182ce18" stroke="#3182ce" stroke-width={1.5} />
                <text x={HALF} y={HALF + 3} text-anchor="middle" font-size="6" font-weight="800" fill="#3182ce">LOX</text>
              {:else if sym.type === 'tank_fuel'}
                <rect x={3} y={3} width={CELL - 6} height={CELL - 6} rx={6} fill="#ed893618" stroke="#ed8936" stroke-width={1.5} />
                <text x={HALF} y={HALF + 3} text-anchor="middle" font-size="6" font-weight="800" fill="#ed8936">FUEL</text>
              {:else if sym.type === 'supply'}
                <polygon points="{HALF},{4} {CELL - 4},{HALF} {HALF},{CELL - 4} {4},{HALF}" fill="#38a16918" stroke="#38a169" stroke-width={1.5} />
                <text x={HALF} y={HALF + 3} text-anchor="middle" font-size="6" font-weight="800" fill="#38a169">GN2</text>
              {/if}
            </svg>
          </div>
          <div class="symbol-info">
            <code class="symbol-code">{sym.label}</code>
            <span class="symbol-desc">{sym.desc}</span>
          </div>
        </div>
      {/each}
    </div>
  </div>

  <div class="legend-card">
    <h2>Pipe Colors (Cell Fill)</h2>
    <p class="legend-intro">
      Set the cell background color in Excel to assign a fluid type.
      This determines the pipe color in the rendered diagram.
    </p>

    <div class="fluid-grid">
      {#each fluids as f}
        <div class="fluid-row">
          <div class="fluid-swatch" style="background: {f.color};"></div>
          <div class="fluid-info">
            <strong>{f.name}</strong>
            <span>{f.desc}</span>
          </div>
        </div>
      {/each}
    </div>
  </div>

  <div class="legend-card">
    <h2>Live Data Mapping</h2>
    <p class="legend-intro">
      Element IDs in the XLSX are automatically mapped to live channels
      from <code>moe/configs/</code> (rocket_pt.json, rocket_dc.json, gse_dc.json, etc.).
      No Config sheet needed in the XLSX.
    </p>
    <table class="config-table">
      <thead>
        <tr>
          <th>XLSX Element</th><th>Maps To</th><th>Source Config</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>PT1 .. PT16</td><td>rocket_panda pt ch 1-16</td><td>rocket_pt.json</td></tr>
        <tr><td>PB1 .. PB16</td><td>rocket_panda dc ch 1-16</td><td>rocket_dc.json</td></tr>
        <tr><td>PB17+ / GSE</td><td>gse_panda dc ch 1-16</td><td>gse_dc.json</td></tr>
        <tr><td>TC1 .. TC16</td><td>rocket_panda tc ch 1-16</td><td>(convention)</td></tr>
        <tr><td>LC1 .. LC16</td><td>rocket_panda lc ch 1-16</td><td>(convention)</td></tr>
      </tbody>
    </table>
  </div>
</div>

<style>
  .legend-view {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 20px;
    max-width: 800px;
    margin: 0 auto;
  }

  .legend-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-lg);
    padding: 20px;
    box-shadow: var(--shadow-sm);
  }
  .legend-card h2 {
    font-size: 16px;
    font-weight: 800;
    color: var(--text-primary);
    margin-bottom: 8px;
  }
  .legend-intro {
    font-size: 13px;
    color: var(--text-tertiary);
    margin-bottom: 16px;
    line-height: 1.4;
  }
  .legend-intro code {
    background: var(--bg-elevated);
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 12px;
    font-family: var(--font-mono);
    border: 1px solid var(--border-light);
  }

  .symbols-grid {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .symbol-row {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 6px;
    border-radius: var(--radius-sm);
    transition: background 0.15s;
  }
  .symbol-row:hover { background: var(--bg-elevated); }

  .symbol-preview {
    flex-shrink: 0;
    border-radius: var(--radius-sm);
    overflow: hidden;
    box-shadow: var(--shadow-sm);
  }

  .symbol-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .symbol-code {
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 700;
    color: var(--text-primary);
    background: var(--bg-elevated);
    padding: 1px 6px;
    border-radius: 3px;
    border: 1px solid var(--border-light);
    display: inline-block;
    width: fit-content;
  }
  .symbol-desc {
    font-size: 12px;
    color: var(--text-tertiary);
  }

  .fluid-grid {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .fluid-row {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .fluid-swatch {
    width: 32px;
    height: 20px;
    border-radius: 4px;
    flex-shrink: 0;
  }
  .fluid-info {
    font-size: 12px;
    color: var(--text-secondary);
  }
  .fluid-info strong {
    margin-right: 6px;
    color: var(--text-primary);
  }

  .config-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    font-family: var(--font-mono);
  }
  .config-table th {
    text-align: left;
    font-weight: 700;
    padding: 6px 10px;
    background: var(--bg-elevated);
    border-bottom: 2px solid var(--border-light);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-tertiary);
  }
  .config-table td {
    padding: 5px 10px;
    border-bottom: 1px solid var(--border-light);
    color: var(--text-secondary);
  }
  .config-table tr:hover td { background: var(--bg-elevated); }
</style>
