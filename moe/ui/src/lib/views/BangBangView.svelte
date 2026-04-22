<script>
  import { onMount, onDestroy } from 'svelte';
  import { devices } from '../stores/devices.js';
  import { wsConnected, sendCommand, onMessage } from '../stores/websocket.js';
  import { showToast } from '../stores/ui.js';

  let canvas;
  let chartRAF;
  
  const BB_CHART_PTS = 300;
  let chartData = {
    lox: new Float32Array(BB_CHART_PTS),
    fuel: new Float32Array(BB_CHART_PTS),
    idx: 0,
    count: 0
  };

  let evtLogs = [];

  // Local state for configuration inputs
  let localConfig = {
    lox: { setpoint: 200, deadband: 10, waitMs: 500, maxOpen: 0, ventTrigger: 0, ventAuto: 0, mdotTarget: 0, spMin: 0, spMax: 0, gain: 0, mdotOn: 0 },
    fuel: { setpoint: 200, deadband: 10, waitMs: 500, maxOpen: 0, ventTrigger: 0, ventAuto: 0, mdotTarget: 0, spMin: 0, spMax: 0, gain: 0, mdotOn: 0 }
  };

  function getDeviceType(bus) {
    // Determine the device from the rocket_panda config info if available
    return 'rocket_panda';
  }

  function pushConfig(bus) {
    if (!$wsConnected) { showToast('Error', 'Not connected', 'error'); return; }
    const device = getDeviceType(bus);
    const cfg = localConfig[bus];

    sendCommand({ 
      action: 'bb_config', device, bus, 
      setpoint: cfg.setpoint, deadband: cfg.deadband, wait_ms: cfg.waitMs, max_open_ms: cfg.maxOpen 
    });

    sendCommand({ 
      action: 'bb_vent_config', device, bus, 
      trigger: cfg.ventTrigger, auto_on: Boolean(cfg.ventAuto) 
    });

    sendCommand({ 
      action: 'bb_mdot_config', device, bus, 
      mdot: cfg.mdotTarget, sp_min: cfg.spMin, sp_max: cfg.spMax, gain: cfg.gain, enable: Boolean(cfg.mdotOn) 
    });

    showToast(`${bus.toUpperCase()} Config Pushed`, 'B+V+M sent to firmware', 'info');
  }

  function toggleEnable(bus, currentState) {
    if (!$wsConnected) { showToast('Error', 'Not connected', 'error'); return; }
    const device = getDeviceType(bus);
    const wantEnable = currentState === 'OFF';
    sendCommand({ action: 'bb_enable', device, bus, enable: wantEnable });
    showToast(`${bus.toUpperCase()} BB`, wantEnable ? 'Enable sent' : 'Disable sent', wantEnable ? 'warning' : 'info');
  }

  function toggleVent(bus, currentlyOpen) {
    if (!$wsConnected) { showToast('Error', 'Not connected', 'error'); return; }
    const device = getDeviceType(bus);
    const wantOpen = !currentlyOpen;
    sendCommand({ action: 'bb_vent', device, bus, open: wantOpen });
    showToast(`${bus.toUpperCase()} Vent`, wantOpen ? 'Open sent' : 'Close sent', 'info');
  }

  function triggerAbort(bus) {
    if (!$wsConnected) { showToast('Error', 'Not connected', 'error'); return; }
    const device = getDeviceType(bus);
    if (typeof Swal !== 'undefined') {
      Swal.fire({
        title: `ABORT ${bus.toUpperCase()}?`,
        text: 'Latched abort — only disarm clears this.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#e53e3e',
        confirmButtonText: 'ABORT'
      }).then(r => {
        if (r.isConfirmed) {
          sendCommand({ action: 'bb_abort', device, bus });
          showToast(`${bus.toUpperCase()} ABORT`, 'Latched abort sent', 'error');
        }
      });
    } else {
      sendCommand({ action: 'bb_abort', device, bus });
      showToast(`${bus.toUpperCase()} ABORT`, 'Latched abort sent', 'error');
    }
  }

  onMount(() => {
    // Add msg handler for EVTs
    const unsub = onMessage(msg => {
      if (msg.type === 'device_message') {
        const line = msg.line || '';
        const evtCls = line.includes('CFG_PUSH') ? 'cfg' : 
                       line.includes('VALVE') ? 'valve' :
                       (line.includes('ABORT') || line.includes('ERROR')) ? 'evt-abort' :
                       line.includes('WARN') ? 'warn' : 'info';
                       
        evtLogs = [{
          time: new Date().toLocaleTimeString(),
          text: line,
          type: evtCls
        }, ...evtLogs.slice(0, 49)]; // keep 50 lines
      }
    });

    chartRAF = window.setInterval(renderChart, 100);

    return () => {
      unsub();
      window.clearInterval(chartRAF);
    };
  });

  $: bbState = $devices['rocket_panda']?.bb || {
    lox: { state: 'OFF', press: false, vent: false, pressure: 0.0, config: {} },
    fuel: { state: 'OFF', press: false, vent: false, pressure: 0.0, config: {} }
  };

  $: {
    // Record into chart ring buffer whenever bbState changes
    const loxP = bbState.lox?.pressure || 0.0;
    const fuelP = bbState.fuel?.pressure || 0.0;
    
    const ci = chartData.idx % BB_CHART_PTS;
    chartData.lox[ci] = loxP;
    chartData.fuel[ci] = fuelP;
    
    chartData.idx++;
    chartData.count = Math.min(chartData.count + 1, BB_CHART_PTS);
  }

  function getBadgeClass(state) {
    if (state === 'SUS') return 'sus';
    if (state === 'AV') return 'av';
    if (state === 'ABT') return 'evt-abort';
    return 'off';
  }

  function getBadgeLabel(state) {
    if (state === 'SUS') return 'SUSTAIN';
    if (state === 'AV') return 'AUTO-VENT';
    if (state === 'ABT') return 'ABORT';
    return 'OFF';
  }

  function renderChart() {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;

    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const n = chartData.count;
    if (n < 2) { 
      ctx.fillStyle = '#8b949e'; 
      ctx.font = '12px monospace'; 
      ctx.textAlign = 'center'; 
      ctx.fillText('Waiting for data...', w / 2, h / 2); 
      return; 
    }

    let yMin = Infinity, yMax = -Infinity;
    for (let i = 0; i < n; i++) {
      const ci = (chartData.idx - n + i + BB_CHART_PTS) % BB_CHART_PTS;
      const lv = chartData.lox[ci];
      const fv = chartData.fuel[ci];
      yMin = Math.min(yMin, lv, fv);
      yMax = Math.max(yMax, lv, fv);
    }
    
    const pad = Math.max((yMax - yMin) * 0.15, 20);
    yMin -= pad;
    yMax += pad;
    const xStep = w / Math.max(n - 1, 1);
    const toY = v => h - ((v - yMin) / (yMax - yMin)) * h;

    // Setpoint bands
    ['lox', 'fuel'].forEach((bus, bi) => {
      const sp = localConfig[bus].setpoint;
      const db = localConfig[bus].deadband;
      const y1 = toY(sp + db / 2);
      const y2 = toY(sp - db / 2);

      ctx.fillStyle = bi === 0 ? 'rgba(99,179,237,0.08)' : 'rgba(246,173,85,0.08)';
      ctx.fillRect(0, Math.min(y1, y2), w, Math.abs(y2 - y1));

      ctx.strokeStyle = bi === 0 ? 'rgba(99,179,237,0.3)' : 'rgba(246,173,85,0.3)';
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, toY(sp));
      ctx.lineTo(w, toY(sp));
      ctx.stroke();
      ctx.setLineDash([]);
    });

    // Grid lines
    ctx.strokeStyle = 'rgba(139,148,158,0.15)';
    ctx.lineWidth = 0.5;
    for(let i=0; i<=4; i++) {
        const y = h * i / 4;
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    }
    
    // Y axis labels
    ctx.fillStyle = '#8b949e';
    ctx.font = '10px monospace';
    ctx.textAlign = 'left';
    for (let i = 0; i <= 4; i++) {
        const v = yMax - (yMax - yMin) * i / 4;
        ctx.fillText(v.toFixed(0) + ' psi', 4, h * i / 4 + 12);
    }

    // Traces
    [{bus: 'lox', color: '#63b3ed'}, {bus: 'fuel', color: '#f6ad55'}].forEach(({bus, color}) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.lineJoin = 'round';
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const ci = (chartData.idx - n + i + BB_CHART_PTS) % BB_CHART_PTS;
        const x = i * xStep;
        const y = toY(chartData[bus][ci]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    });
  }

</script>

<div class="bb-tab-layout">
  {#each ['lox', 'fuel'] as bus}
    <div class="bb-tab-card {bus}" class:active={bbState[bus].state === 'SUS' || bbState[bus].state === 'AV'} class:bb-abort={bbState[bus].state === 'ABT'}>
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div class="bb-card-title">
          <i class="fas {bus === 'lox' ? 'fa-snowflake' : 'fa-fire'}"></i> {bus.toUpperCase()} Bus
        </div>
        <span class="bb-state-badge {getBadgeClass(bbState[bus].state)}">
          <span class="bb-state-dot"></span> <span>{getBadgeLabel(bbState[bus].state)}</span>
        </span>
      </div>

      <!-- Live readings -->
      <div class="bb-live-row">
        <div class="bb-live-psi {bbState[bus].pressure > localConfig[bus].setpoint + localConfig[bus].deadband/2 ? 'hi' : (bbState[bus].pressure < localConfig[bus].setpoint - localConfig[bus].deadband/2 ? 'lo' : '')}">
          {bbState[bus].pressure.toFixed(1)} psi
        </div>
        <div class="bb-sol-indicators">
          <div class="bb-sol">
            <div class="bb-sol-dot {bbState[bus].press ? 'active' : ''}"></div> Press
          </div>
          <div class="bb-sol">
            <div class="bb-sol-dot {bbState[bus].vent ? 'active' : ''}"></div> Vent
          </div>
        </div>
      </div>

      <!-- Config: Core -->
      <div class="bb-cfg-group">
        <div class="bb-cfg-group-title"><i class="fas fa-crosshairs"></i> Core Config</div>
        <div class="bb-config-grid">
          <div class="bb-cfg-field"><label>Setpoint (PSI)</label><input type="number" bind:value={localConfig[bus].setpoint} step="5" min="0"></div>
          <div class="bb-cfg-field"><label>Deadband (PSI)</label><input type="number" bind:value={localConfig[bus].deadband} step="1" min="1"></div>
          <div class="bb-cfg-field"><label>Wait (ms)</label><input type="number" bind:value={localConfig[bus].waitMs} step="100" min="0"></div>
          <div class="bb-cfg-field"><label>Max Open (ms)</label><input type="number" bind:value={localConfig[bus].maxOpen} step="100" min="0"></div>
        </div>
      </div>

      <!-- Config: Vent -->
      <div class="bb-cfg-group">
        <div class="bb-cfg-group-title"><i class="fas fa-wind"></i> Vent Config</div>
        <div class="bb-config-grid">
          <div class="bb-cfg-field"><label>Trigger (PSI)</label><input type="number" bind:value={localConfig[bus].ventTrigger} step="5" min="0"></div>
          <div class="bb-cfg-field"><label>Auto-Vent</label>
            <select bind:value={localConfig[bus].ventAuto}>
              <option value={0}>Off</option><option value={1}>On</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Config: Mdot -->
      <div class="bb-cfg-group">
        <div class="bb-cfg-group-title"><i class="fas fa-tachometer-alt"></i> Mass-Flow Config</div>
        <div class="bb-config-grid three">
          <div class="bb-cfg-field"><label>Target</label><input type="number" bind:value={localConfig[bus].mdotTarget} step="1" min="0"></div>
          <div class="bb-cfg-field"><label>SP Min</label><input type="number" bind:value={localConfig[bus].spMin} step="5" min="0"></div>
          <div class="bb-cfg-field"><label>SP Max</label><input type="number" bind:value={localConfig[bus].spMax} step="5" min="0"></div>
          <div class="bb-cfg-field"><label>Gain</label><input type="number" bind:value={localConfig[bus].gain} step="1" min="0"></div>
          <div class="bb-cfg-field"><label>Enable</label>
            <select bind:value={localConfig[bus].mdotOn}>
              <option value={0}>Off</option><option value={1}>On</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Buttons -->
      <div class="bb-btn-row">
        <button class="bb-action-btn push" on:click={() => pushConfig(bus)}>
          <i class="fas fa-upload"></i> Push Config
        </button>
        <button class="bb-action-btn {bbState[bus].state !== 'OFF' ? 'disable' : 'enable'}" on:click={() => toggleEnable(bus, bbState[bus].state)}>
          <i class="fas {bbState[bus].state !== 'OFF' ? 'fa-stop' : 'fa-play'}"></i> 
          {bbState[bus].state !== 'OFF' ? 'Disable' : 'Enable'}
        </button>
        <button class="bb-action-btn vent" on:click={() => toggleVent(bus, bbState[bus].vent)}>
          <i class="fas fa-wind"></i> {bbState[bus].vent ? 'Close Vent' : 'Vent'}
        </button>
        <button class="bb-action-btn evt-abort" on:click={() => triggerAbort(bus)}>
          <i class="fas fa-skull-crossbones"></i> Abort
        </button>
      </div>
    </div>
  {/each}

  <!-- Pressure Chart -->
  <div class="bb-chart-container">
    <div class="bb-chart-header">
      <span><i class="fas fa-chart-area"></i> Pressure History (30s)</span>
      <span>— <span style="color:#63b3ed">LOX</span> — <span style="color:#f6ad55">Fuel</span></span>
    </div>
    <canvas bind:this={canvas} class="bb-chart-canvas"></canvas>
  </div>

  <!-- Event Log -->
  <div class="bb-evt-container">
    <div class="bb-evt-header">
      <span><i class="fas fa-scroll"></i> EVT Audit Log</span>
      <button style="background:none;border:none;color:#58a6ff;cursor:pointer;font-size:11px" on:click={() => evtLogs = []}>
        <i class="fas fa-eraser"></i> Clear
      </button>
    </div>
    <div class="bb-evt-body">
      {#each evtLogs as log}
        <div class="bb-evt-line {log.type}">[{log.time}] {log.text}</div>
      {/each}
    </div>
  </div>
</div>

<style>
  .bb-tab-layout { 
    display: grid; 
    grid-template-columns: 1fr 1fr; 
    gap: 14px; 
    padding: 16px; 
    height: 100%; 
    overflow-y: auto; 
    background: #f8fafc;
  }
  .bb-tab-card {
    background: white; border: 2px solid #cbd5e0; border-radius: 10px;
    padding: 14px; display: flex; flex-direction: column; gap: 10px;
  }
  .bb-tab-card.lox  { border-color: #63b3ed; }
  .bb-tab-card.fuel { border-color: #f6ad55; }
  .bb-tab-card.lox.active  { border-color: #3182ce; box-shadow: 0 0 12px rgba(49,130,206,0.25); }
  .bb-tab-card.fuel.active { border-color: #dd6b20; box-shadow: 0 0 12px rgba(221,107,32,0.25); }
  .bb-tab-card.evt-abort { border-color: #e53e3e; box-shadow: 0 0 16px rgba(229,62,62,0.4); }
  .bb-card-title { font-weight: 800; font-size: 16px; display: flex; align-items: center; gap: 6px; }
  
  .bb-state-badge {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 12px; border-radius: 16px; font-weight: 700; font-size: 12px;
    text-transform: uppercase; letter-spacing: 0.05em;
  }
  .bb-state-badge.off { background: #edf2f7; color: #718096; }
  .bb-state-badge.sus { background: #c6f6d5; color: #22543d; }
  .bb-state-badge.av  { background: #fefcbf; color: #744210; }
  .bb-state-badge.evt-abort { background: #fed7d7; color: #9b2c2c; animation: pulse 1s infinite; }
  
  .bb-state-dot { width: 8px; height: 8px; border-radius: 50%; }
  .bb-state-badge.off .bb-state-dot { background: #a0aec0; }
  .bb-state-badge.sus .bb-state-dot { background: #38a169; box-shadow: 0 0 4px #38a169; }
  .bb-state-badge.av  .bb-state-dot { background: #d69e2e; box-shadow: 0 0 4px #d69e2e; }
  .bb-state-badge.evt-abort .bb-state-dot { background: #e53e3e; box-shadow: 0 0 6px #e53e3e; }
  
  .bb-config-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
  .bb-config-grid.three { grid-template-columns: 1fr 1fr 1fr; }
  .bb-cfg-group { background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px 10px; }
  .bb-cfg-group-title {
    font-size: 11px; font-weight: 700; color: #4a5568; text-transform: uppercase;
    margin-bottom: 6px; display: flex; align-items: center; gap: 6px;
  }
  .bb-cfg-field label { display: block; font-size: 10px; color: #718096; margin-bottom: 2px; font-weight: 600; }
  .bb-cfg-field input, .bb-cfg-field select {
    width: 100%; padding: 4px 6px; border: 1px solid #e2e8f0; border-radius: 4px; border-style: solid;
    font-size: 12px; font-weight: bold; background: white;
  }
  
  .bb-live-row { display: flex; gap: 8px; align-items: center; }
  .bb-live-psi {
    font-size: 22px; font-weight: 800; font-family: 'Consolas','Fira Code',monospace;
    color: #2d3748; min-width: 100px;
  }
  .bb-live-psi.hi { color: #e53e3e; }
  .bb-live-psi.lo { color: #3182ce; }
  .bb-sol-indicators { display: flex; gap: 12px; }
  .bb-sol { display: flex; align-items: center; gap: 4px; font-size: 11px; font-weight: 600; }
  .bb-sol-dot { width: 10px; height: 10px; border-radius: 50%; border: 2px solid #cbd5e0; background: #edf2f7; }
  .bb-sol-dot.active { background: #38a169; border-color: #38a169; box-shadow: 0 0 6px rgba(56,161,105,0.5); }
  
  .bb-btn-row { display: flex; gap: 6px; flex-wrap: wrap; }
  .bb-action-btn {
    flex: 1; min-width: 80px; padding: 8px 6px; border: none; border-radius: 6px;
    font-weight: bold; font-size: 11px; cursor: pointer; transition: all 0.15s;
    display: flex; align-items: center; justify-content: center; gap: 4px;
  }
  .bb-action-btn.enable  { background: #38a169; color: white; }
  .bb-action-btn.enable:hover  { background: #2f855a; }
  .bb-action-btn.disable { background: #718096; color: white; }
  .bb-action-btn.disable:hover { background: #4a5568; }
  .bb-action-btn.vent    { background: #3182ce; color: white; }
  .bb-action-btn.vent:hover    { background: #2c5282; }
  .bb-action-btn.evt-abort { background: #e53e3e; color: white; }
  .bb-action-btn.evt-abort:hover { background: #c53030; }
  .bb-action-btn.push    { background: #2d3748; color: #e2e8f0; }
  .bb-action-btn.push:hover    { background: #4a5568; }
  
  .bb-chart-container {
    grid-column: 1 / -1; background: #0d1117; border-radius: 10px;
    padding: 10px; border: 1px solid #1f2933; margin-top: 10px;
  }
  .bb-chart-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 6px; color: #8b949e; font-size: 11px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.06em;
  }
  .bb-chart-canvas { width: 100%; height: 180px; border-radius: 6px; }
  
  .bb-evt-container {
    grid-column: 1 / -1; background: #0d1117; border-radius: 10px;
    padding: 10px; border: 1px solid #1f2933; max-height: 200px;
  }
  .bb-evt-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 6px; color: #8b949e; font-size: 11px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.06em;
  }
  .bb-evt-body {
    overflow-y: auto; max-height: 160px; font-family: 'Fira Code','Consolas',monospace;
    font-size: 11px; line-height: 1.5;
  }
  .bb-evt-line { margin: 0; padding: 1px 4px; border-radius: 2px; }
  .bb-evt-line.cfg  { color: #79c0ff; }
  .bb-evt-line.valve { color: #7ee787; }
  .bb-evt-line.evt-abort { color: #ff7b72; font-weight: bold; }
  .bb-evt-line.warn  { color: #d29922; }
  .bb-evt-line.info  { color: #8b949e; }
  
  @keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.5; }
    100% { opacity: 1; }
  }
</style>
