<script>
  import SensorCard from '../components/SensorCard.svelte';
  import Sparkline from '../components/Sparkline.svelte';
  import DCChannel from '../components/DCChannel.svelte';
  import { devices } from '../stores/devices.js';
  import { sensorStatus, formatValue } from '../utils/format.js';

  // Key PT channels to show in overview
  const keyPts = [
    { deviceId: 'rocket_panda', ch: '1', label: 'LOX TANK' },
    { deviceId: 'rocket_panda', ch: '2', label: 'FUEL TANK' },
    { deviceId: 'rocket_panda', ch: '5', label: 'CHAMBER' },
    { deviceId: 'gse_panda', ch: '1', label: 'LOX SUPPLY' },
    { deviceId: 'gse_panda', ch: '2', label: 'FUEL SUPPLY' },
    { deviceId: 'gse_panda', ch: '5', label: 'PRESS GSE' },
    { deviceId: 'rocket_panda', ch: '10', label: 'PRESSURANT' },
    { deviceId: 'gse_panda', ch: '7', label: 'WATER SUPPLY' },
  ];

  // Key valves to show
  const keyValves = [
    { deviceId: 'gse_panda', ch: '1', name: 'LOX FILL', short: 'lox_fill', type: 'fill' },
    { deviceId: 'gse_panda', ch: '2', name: 'FUEL FILL', short: 'fuel_fill', type: 'fill' },
    { deviceId: 'gse_panda', ch: '7', name: 'PRESSURANT', short: 'press', type: 'pressurize' },
    { deviceId: 'rocket_panda', ch: '1', name: 'LOX MAIN', short: 'lox_main', type: 'run_valve' },
    { deviceId: 'rocket_panda', ch: '2', name: 'FUEL MAIN', short: 'fuel_main', type: 'run_valve' },
    { deviceId: 'rocket_panda', ch: '3', name: 'IGNITER', short: 'igniter', type: 'ignition' },
  ];

  $: ptReadouts = keyPts.map(p => {
    const d = $devices[p.deviceId];
    const reading = d?.pt?.[p.ch];
    return {
      ...p,
      value: reading?.value,
      units: reading?.units || 'psi',
      name: reading?.name || p.label,
      status: sensorStatus(reading?.value, { range: [0, 500] }),
      history: devices.getPtHistory(p.deviceId, p.ch),
    };
  });

  $: lcReadouts = Object.entries($devices['rocket_panda']?.lc || {}).slice(0, 4).map(([ch, data]) => ({
    ch,
    name: data.name || `LC${ch}`,
    value: data.value,
    units: data.units || 'lbf',
    status: sensorStatus(data.value, null),
    history: devices.getLcHistory('rocket_panda', ch),
  }));

  $: valveReadouts = keyValves.map(v => {
    const d = $devices[v.deviceId];
    const dc = d?.dc?.[v.ch];
    return {
      ...v,
      state: dc?.state || false,
      current: dc?.value || 0,
      armed: d?.armed ?? false,
    };
  });

  $: rocketConnected = $devices['rocket_panda']?.connected ?? false;
  $: gseConnected = $devices['gse_panda']?.connected ?? false;
  $: daqConnected = $devices['ni_daq']?.connected ?? false;
</script>

<div class="overview-layout">
  <!-- Left: Key pressures -->
  <div class="overview-panel panel-main">
    <div class="panel-header">
      <span class="panel-title">Key Pressures</span>
      <span class="panel-subtitle">{ptReadouts.length} sensors</span>
    </div>
    <div class="sensor-grid-overview">
      {#each ptReadouts as pt}
        <SensorCard
          name={pt.name}
          shortName={pt.label}
          value={pt.value}
          units={pt.units}
          status={pt.status}
          history={pt.history}
          channelId={pt.ch}
          type="pt"
        />
      {/each}
    </div>
  </div>

  <!-- Middle: System status + mini P&ID -->
  <div class="overview-center">
    <div class="overview-panel panel-status">
      <div class="panel-header">
        <span class="panel-title">System Status</span>
      </div>
      <div class="status-cards">
        <div class="status-card" class:ok={rocketConnected}>
          <div class="status-device">ROCKET</div>
          <div class="status-state">{rocketConnected ? 'ONLINE' : 'OFFLINE'}</div>
        </div>
        <div class="status-card" class:ok={gseConnected}>
          <div class="status-device">GSE</div>
          <div class="status-state">{gseConnected ? 'ONLINE' : 'OFFLINE'}</div>
        </div>
        <div class="status-card" class:ok={daqConnected}>
          <div class="status-device">DAQ</div>
          <div class="status-state">{daqConnected ? 'ONLINE' : 'OFFLINE'}</div>
        </div>
      </div>
    </div>

    <div class="overview-panel panel-loads">
      <div class="panel-header">
        <span class="panel-title">Load Cells</span>
      </div>
      <div class="sensor-list-compact">
        {#each lcReadouts as lc}
          <SensorCard
            name={lc.name}
            shortName="LC{lc.ch}"
            value={lc.value}
            units={lc.units}
            status={lc.status}
            history={lc.history}
            channelId={lc.ch}
            type="lc"
          />
        {/each}
      </div>
    </div>

    <div class="overview-panel panel-pid-mini">
      <div class="panel-header">
        <span class="panel-title">P&ID</span>
      </div>
      <img src="pid_v14.png" alt="MOE P&ID mini" class="mini-pid" />
    </div>
  </div>

  <!-- Right: Key valves -->
  <div class="overview-panel panel-valves">
    <div class="panel-header">
      <span class="panel-title">Key Valves</span>
    </div>
    <div class="valve-list-overview">
      {#each valveReadouts as v}
        <DCChannel
          name={v.name}
          shortName={v.short}
          channelId={parseInt(v.ch)}
          device={v.deviceId}
          type={v.type}
          state={v.state}
          current={v.current}
          armed={v.armed}
        />
      {/each}
    </div>
  </div>
</div>

<style>
  .overview-layout {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr 1fr 280px;
    gap: 2px;
    padding: 2px;
    background: var(--border-light);
    overflow: hidden;
  }

  .overview-panel {
    background: var(--bg-surface);
    border-radius: var(--radius-sm);
    padding: 8px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .overview-center {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border-light);
    margin-bottom: 6px;
    flex-shrink: 0;
  }
  .panel-title {
    font-weight: 700;
    font-size: 11px;
    color: var(--text-primary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .panel-subtitle {
    font-size: 9px;
    color: var(--text-muted);
  }

  .sensor-grid-overview {
    display: flex;
    flex-direction: column;
    gap: 4px;
    overflow-y: auto;
    flex: 1;
  }

  .sensor-list-compact {
    display: flex;
    flex-direction: column;
    gap: 4px;
    overflow-y: auto;
  }

  .valve-list-overview {
    display: flex;
    flex-direction: column;
    gap: 6px;
    overflow-y: auto;
    flex: 1;
  }

  /* System status cards */
  .status-cards {
    display: flex;
    gap: 6px;
  }
  .status-card {
    flex: 1;
    padding: 10px;
    background: #fef2f2;
    border-radius: var(--radius-sm);
    text-align: center;
    border: 1px solid var(--red-500);
    transition: all 0.3s;
  }
  .status-card.ok {
    background: #f0fff4;
    border-color: var(--green-600);
  }
  .status-device {
    font-size: 10px;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: 0.5px;
  }
  .status-state {
    font-size: 10px;
    font-weight: 600;
    margin-top: 2px;
  }
  .status-card.ok .status-state { color: var(--green-600); }
  .status-card:not(.ok) .status-state { color: var(--red-500); }

  .mini-pid {
    width: 100%;
    border-radius: var(--radius-sm);
    object-fit: contain;
    opacity: 0.9;
    flex: 1;
    min-height: 0;
  }

  .panel-main {
    min-height: 0;
  }
  .panel-pid-mini {
    flex: 1;
    min-height: 0;
  }
</style>
