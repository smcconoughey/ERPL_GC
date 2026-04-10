<script>
  import { devices } from '../stores/devices.js';
  import { sendCommand } from '../stores/websocket.js';
  import { showToast } from '../stores/ui.js';
  import { formatValue } from '../utils/format.js';

  $: gseDc = $devices['gse_panda']?.dc || {};
  $: gsePt = $devices['gse_panda']?.pt || {};
  $: rocketDc = $devices['rocket_panda']?.dc || {};
  $: rocketPt = $devices['rocket_panda']?.pt || {};
  $: rocketLc = $devices['rocket_panda']?.lc || {};
  $: gseArmed = $devices['gse_panda']?.armed ?? false;
  $: rocketArmed = $devices['rocket_panda']?.armed ?? false;

  // PT Sensor overlay positions mapped to the P&ID image (percentages)
  // These are approximate positions based on the MOE P&ID V1.4
  const ptOverlays = [
    // GSE PTs
    { id: 'gse_pt_1', label: 'LOX SUPPLY', deviceId: 'gse_panda', ch: '1', x: 28, y: 58 },
    { id: 'gse_pt_2', label: 'FUEL SUPPLY', deviceId: 'gse_panda', ch: '2', x: 52, y: 39 },
    { id: 'gse_pt_3', label: 'LOX FLOW', deviceId: 'gse_panda', ch: '3', x: 28, y: 79 },
    { id: 'gse_pt_4', label: 'FUEL FLOW', deviceId: 'gse_panda', ch: '4', x: 68, y: 79 },
    { id: 'gse_pt_5', label: 'PRESS GSE', deviceId: 'gse_panda', ch: '5', x: 14, y: 69 },
    { id: 'gse_pt_6', label: 'AMBIENT', deviceId: 'gse_panda', ch: '6', x: 5, y: 79 },
    // Rocket PTs
    { id: 'rkt_pt_1', label: 'LOX TANK', deviceId: 'rocket_panda', ch: '1', x: 42, y: 55 },
    { id: 'rkt_pt_2', label: 'FUEL TANK', deviceId: 'rocket_panda', ch: '2', x: 52, y: 30 },
    { id: 'rkt_pt_5', label: 'CHAMBER', deviceId: 'rocket_panda', ch: '5', x: 45, y: 89 },
    { id: 'rkt_pt_10', label: 'PRESSURANT', deviceId: 'rocket_panda', ch: '10', x: 32, y: 18 },
  ];

  // GSE Valve overlays mapped to P&ID positions
  const valveOverlays = [
    { id: 'gse_v1', label: 'LOX FILL', deviceId: 'gse_panda', ch: '1', x: 22, y: 63, color: 'lox' },
    { id: 'gse_v2', label: 'FUEL FILL', deviceId: 'gse_panda', ch: '2', x: 72, y: 63, color: 'fuel' },
    { id: 'gse_v3', label: 'LOX DRAIN', deviceId: 'gse_panda', ch: '3', x: 22, y: 68, color: 'lox' },
    { id: 'gse_v4', label: 'FUEL DRAIN', deviceId: 'gse_panda', ch: '4', x: 72, y: 68, color: 'fuel' },
    { id: 'gse_v5', label: 'LOX VENT', deviceId: 'gse_panda', ch: '5', x: 18, y: 58, color: 'vent' },
    { id: 'gse_v6', label: 'FUEL VENT', deviceId: 'gse_panda', ch: '6', x: 76, y: 58, color: 'vent' },
    { id: 'gse_v7', label: 'PRESS', deviceId: 'gse_panda', ch: '7', x: 34, y: 28, color: 'gn2' },
    { id: 'gse_v12', label: 'QD', deviceId: 'gse_panda', ch: '12', x: 36, y: 59, color: 'gn2' },
    // Rocket valves
    { id: 'rkt_v1', label: 'LOX MAIN', deviceId: 'rocket_panda', ch: '1', x: 37, y: 78, color: 'lox' },
    { id: 'rkt_v2', label: 'FUEL MAIN', deviceId: 'rocket_panda', ch: '2', x: 57, y: 78, color: 'fuel' },
    { id: 'rkt_v3', label: 'IGNITER', deviceId: 'rocket_panda', ch: '3', x: 47, y: 87, color: 'fire' },
  ];

  function getPtValue(overlay) {
    const d = $devices[overlay.deviceId];
    if (!d || !d.pt || !d.pt[overlay.ch]) return null;
    return d.pt[overlay.ch]?.value;
  }

  function getValveState(overlay) {
    const d = $devices[overlay.deviceId];
    if (!d || !d.dc || !d.dc[overlay.ch]) return false;
    return d.dc[overlay.ch]?.state || false;
  }

  function toggleValve(overlay) {
    const armed = overlay.deviceId === 'gse_panda' ? gseArmed : rocketArmed;
    if (!armed) {
      showToast('Not Armed', 'Arm the system before actuating valves', 'warning');
      return;
    }
    const currentState = getValveState(overlay);
    const newState = currentState ? 0 : 1;
    sendCommand({
      action: 'send',
      device: overlay.deviceId,
      command: `s${overlay.ch}${newState}.00000`
    });
    showToast(overlay.label, newState ? 'OPENED' : 'CLOSED', newState ? 'success' : 'warning');
  }
</script>

<div class="pid-layout">
  <div class="pid-container">
    <div class="pid-image-wrap">
      <img src="pid_v14.png" alt="MOE P&ID V1.4" class="pid-image" />
      
      <!-- PT Sensor Overlays -->
      {#each ptOverlays as pt}
        {@const val = getPtValue(pt)}
        <div
          class="pt-overlay"
          style="left: {pt.x}%; top: {pt.y}%;"
          title="{pt.label}"
        >
          <span class="pt-val">{val !== null ? formatValue(val, 0) : '--'}</span>
          <span class="pt-unit">psi</span>
        </div>
      {/each}

      <!-- Valve Overlays -->
      {#each valveOverlays as valve}
        {@const isOpen = getValveState(valve)}
        <button
          class="valve-overlay valve-{valve.color}"
          class:open={isOpen}
          class:closed={!isOpen}
          style="left: {valve.x}%; top: {valve.y}%;"
          title="{valve.label}: {isOpen ? 'OPEN' : 'CLOSED'}"
          on:click={() => toggleValve(valve)}
        >
          <span class="valve-label">{valve.label}</span>
          <span class="valve-state-badge">{isOpen ? 'OPEN' : 'SHUT'}</span>
        </button>
      {/each}
    </div>
  </div>

  <!-- Sidebar with readings list -->
  <div class="pid-sidebar">
    <div class="sidebar-section">
      <div class="sidebar-title">GSE Pressures</div>
      <div class="readings-list">
        {#each Object.entries(gsePt).slice(0, 8) as [ch, data]}
          <div class="reading-row">
            <span class="reading-name">{data.name || `PT${ch}`}</span>
            <span class="reading-val">{formatValue(data.value, 0)}</span>
          </div>
        {/each}
      </div>
    </div>
    <div class="sidebar-section">
      <div class="sidebar-title">Rocket Pressures</div>
      <div class="readings-list">
        {#each Object.entries(rocketPt).slice(0, 12) as [ch, data]}
          <div class="reading-row">
            <span class="reading-name">{data.name || `PT${ch}`}</span>
            <span class="reading-val">{formatValue(data.value, 0)}</span>
          </div>
        {/each}
      </div>
    </div>
    <div class="sidebar-section">
      <div class="sidebar-title">Weights</div>
      <div class="readings-list">
        {#each Object.entries(rocketLc).slice(0, 6) as [ch, data]}
          <div class="reading-row">
            <span class="reading-name">{data.name || `LC${ch}`}</span>
            <span class="reading-val">{formatValue(data.value, 0)} lbf</span>
          </div>
        {/each}
      </div>
    </div>
    <div class="sidebar-section">
      <div class="sidebar-title">GSE Valves</div>
      <div class="readings-list">
        {#each Object.entries(gseDc).slice(0, 12) as [ch, data]}
          <div class="reading-row">
            <span class="reading-name">DC{ch}</span>
            <span class="valve-dot" class:on={data.state}></span>
          </div>
        {/each}
      </div>
    </div>
  </div>
</div>

<style>
  .pid-layout {
    flex: 1;
    display: flex;
    overflow: hidden;
    background: var(--border-light);
    gap: 2px;
  }

  .pid-container {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-surface);
    position: relative;
    overflow: hidden;
    padding: 8px;
  }

  .pid-image-wrap {
    position: relative;
    max-width: 100%;
    max-height: 100%;
  }

  .pid-image {
    display: block;
    max-width: 100%;
    max-height: calc(100vh - 130px);
    object-fit: contain;
    border-radius: var(--radius-sm);
    box-shadow: var(--shadow-md);
  }

  /* PT sensor overlays */
  .pt-overlay {
    position: absolute;
    transform: translate(-50%, -50%);
    background: rgba(255, 255, 255, 0.92);
    border: 2px solid var(--blue-500);
    border-radius: var(--radius-sm);
    padding: 2px 6px;
    display: flex;
    gap: 3px;
    align-items: baseline;
    font-family: var(--font-mono);
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    pointer-events: none;
    z-index: 10;
    white-space: nowrap;
  }
  .pt-val {
    font-size: 12px;
    font-weight: 700;
    color: var(--blue-500);
  }
  .pt-unit {
    font-size: 8px;
    color: var(--text-tertiary);
  }

  /* Valve overlays */
  .valve-overlay {
    position: absolute;
    transform: translate(-50%, -50%);
    border: 2px solid var(--text-muted);
    border-radius: var(--radius-sm);
    padding: 3px 8px;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
    z-index: 10;
    transition: all 0.2s;
    font-family: var(--font-sans);
    background: rgba(255, 255, 255, 0.9);
    box-shadow: 0 2px 8px rgba(0,0,0,0.12);
  }
  .valve-overlay:hover {
    box-shadow: 0 4px 16px rgba(0,0,0,0.2);
    transform: translate(-50%, -50%) scale(1.08);
  }
  .valve-overlay.open {
    border-color: var(--green-600);
    background: rgba(240, 255, 244, 0.95);
  }
  .valve-overlay.closed { border-color: var(--red-500); }

  .valve-label { font-size: 8px; font-weight: 700; color: var(--text-primary); white-space: nowrap; }
  .valve-state-badge {
    font-size: 7px;
    font-weight: 700;
    padding: 1px 4px;
    border-radius: 3px;
  }
  .valve-overlay.open .valve-state-badge { background: var(--green-600); color: white; }
  .valve-overlay.closed .valve-state-badge { background: var(--text-muted); color: white; }

  /* Sidebar */
  .pid-sidebar {
    width: 200px;
    background: var(--bg-surface);
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    flex-shrink: 0;
    font-size: 10px;
  }
  .sidebar-section {
    padding: 8px;
    border-bottom: 1px solid var(--border-light);
  }
  .sidebar-title {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--text-tertiary);
    letter-spacing: 0.6px;
    margin-bottom: 4px;
  }
  .readings-list {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .reading-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 2px 0;
    font-family: var(--font-mono);
  }
  .reading-name {
    font-size: 9px;
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 120px;
  }
  .reading-val {
    font-size: 10px;
    font-weight: 700;
    color: var(--blue-500);
  }
  .valve-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--red-500);
  }
  .valve-dot.on { background: var(--green-600); box-shadow: 0 0 4px var(--green-600); }
</style>
