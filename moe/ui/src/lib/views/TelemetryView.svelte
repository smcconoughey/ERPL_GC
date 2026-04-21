<script>
  import { onMount } from 'svelte';
  import SensorCard from '../components/SensorCard.svelte';
  import { devices } from '../stores/devices.js';
  import { sensorStatus } from '../utils/format.js';

  // per-device TC metadata { deviceId: { channelId: { chill_threshold } } }
  let tcMeta = {};

  onMount(async () => {
    const host = window.location.hostname || 'localhost';
    const base = `http://${host}:8081/configs`;
    const files = {
      rocket_panda: 'rocket_panda_tc.json',
      gse_panda: 'gse_panda_tc.json',
      ni_daq: 'ni_daq_tc.json',
    };
    const results = await Promise.all(
      Object.entries(files).map(async ([dev, path]) => {
        try {
          const r = await fetch(`${base}/${path}`, { cache: 'no-store' });
          if (!r.ok) return [dev, null];
          return [dev, await r.json()];
        } catch { return [dev, null]; }
      })
    );
    const next = {};
    for (const [dev, json] of results) {
      if (!json || !Array.isArray(json.channels)) continue;
      next[dev] = {};
      for (const entry of json.channels) {
        const t = entry.tc;
        if (!t) continue;
        next[dev][t.id] = { chill_threshold: t.chill_threshold ?? null };
      }
    }
    tcMeta = next;
  });

  function ptChannels(deviceId) {
    const d = $devices[deviceId];
    if (!d || !d.pt) return [];
    return Object.entries(d.pt).map(([ch, data]) => ({
      ch,
      name: data.name || `PT${ch}`,
      value: data.value,
      units: data.units || 'psi',
      status: sensorStatus(data.value, { range: [0, 500] }),
      history: devices.getPtHistory(deviceId, ch),
    })).sort((a, b) => parseInt(a.ch) - parseInt(b.ch));
  }

  function lcChannels(deviceId) {
    const d = $devices[deviceId];
    if (!d || !d.lc) return [];
    return Object.entries(d.lc).map(([ch, data]) => ({
      ch,
      name: data.name || `LC${ch}`,
      value: data.value,
      units: data.units || 'lbf',
      status: sensorStatus(data.value, null),
      history: devices.getLcHistory(deviceId, ch),
    })).sort((a, b) => parseInt(a.ch) - parseInt(b.ch));
  }

  function tcChannels(deviceId) {
    const d = $devices[deviceId];
    if (!d || !d.tc) return [];
    const meta = tcMeta[deviceId] || {};
    return Object.entries(d.tc).map(([ch, data]) => ({
      ch,
      name: data.name || `TC${ch}`,
      value: data.value,
      units: data.units || 'degF',
      status: sensorStatus(data.value, null),
      history: devices.getTcHistory(deviceId, ch),
      chillThreshold: meta[ch]?.chill_threshold ?? null,
    })).sort((a, b) => parseInt(a.ch) - parseInt(b.ch));
  }

  $: rocketPtCh = ptChannels('rocket_panda');
  $: gsePtCh = ptChannels('gse_panda');
  $: rocketLcCh = lcChannels('rocket_panda');
  $: rocketTcCh = tcChannels('rocket_panda');
  $: gseTcCh = tcChannels('gse_panda');
  $: niDaqTcCh = (tcMeta, tcChannels('ni_daq'));
</script>

<div class="telemetry-layout">
  <!-- PT Section -->
  <div class="telem-section section-pt">
    <div class="section-header">
      <span class="section-title">Pressure Transducers</span>
      <span class="section-count">{rocketPtCh.length + gsePtCh.length} channels</span>
    </div>

    <div class="device-group">
      <div class="device-label">ROCKET PANDA</div>
      <div class="sensor-grid">
        {#each rocketPtCh as ch (ch.ch)}
          <SensorCard
            name={ch.name}
            shortName="PT{ch.ch}"
            value={ch.value}
            units={ch.units}
            status={ch.status}
            history={ch.history}
            channelId={ch.ch}
            type="pt"
          />
        {/each}
      </div>
    </div>

    <div class="device-group">
      <div class="device-label">GSE PANDA</div>
      <div class="sensor-grid">
        {#each gsePtCh as ch (ch.ch)}
          <SensorCard
            name={ch.name}
            shortName="PT{ch.ch}"
            value={ch.value}
            units={ch.units}
            status={ch.status}
            history={ch.history}
            channelId={ch.ch}
            type="pt"
          />
        {/each}
      </div>
    </div>
  </div>

  <!-- LC + TC Section -->
  <div class="telem-sidebar">
    <div class="telem-section section-lc">
      <div class="section-header">
        <span class="section-title">Load Cells</span>
        <span class="section-count">{rocketLcCh.length} ch</span>
      </div>
      <div class="sensor-list">
        {#each rocketLcCh as ch (ch.ch)}
          <SensorCard
            name={ch.name}
            shortName="LC{ch.ch}"
            value={ch.value}
            units={ch.units}
            status={ch.status}
            history={ch.history}
            channelId={ch.ch}
            type="lc"
          />
        {/each}
      </div>
    </div>

    <div class="telem-section section-tc">
      <div class="section-header">
        <span class="section-title">Thermocouples</span>
        <span class="section-count">{rocketTcCh.length} ch</span>
      </div>
      <div class="sensor-list">
        {#each rocketTcCh as ch (ch.ch)}
          <SensorCard
            name={ch.name}
            shortName="TC{ch.ch}"
            value={ch.value}
            units={ch.units}
            status={ch.status}
            history={ch.history}
            channelId={ch.ch}
            type="tc"
          />
        {/each}
      </div>
    </div>
  </div>
</div>

<style>
  .telemetry-layout {
    flex: 1;
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 2px;
    padding: 2px;
    height: 100%;
    overflow: hidden;
    background: var(--border-light);
  }
  .telem-section {
    background: var(--bg-surface);
    border-radius: var(--radius-sm);
    padding: 8px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .telem-sidebar {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border-light);
    margin-bottom: 6px;
    flex-shrink: 0;
  }
  .section-title {
    font-weight: 700;
    font-size: 12px;
    color: var(--text-primary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .section-count {
    font-size: 10px;
    color: var(--text-muted);
  }
  .device-group {
    margin-bottom: 8px;
  }
  .device-label {
    font-size: 9px;
    font-weight: 700;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 4px;
    padding-left: 4px;
  }
  .sensor-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 4px;
    overflow-y: auto;
  }
  .sensor-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    overflow-y: auto;
    flex: 1;
  }
</style>
