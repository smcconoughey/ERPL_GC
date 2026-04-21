<script>
  import { onMount } from 'svelte';
  import DCChannel from '../components/DCChannel.svelte';
  import { devices } from '../stores/devices.js';
  import { sendCommand } from '../stores/websocket.js';
  import { showToast } from '../stores/ui.js';

  // GSE DC channel metadata (fallback if JSON config can't be fetched)
  const gseDcMeta = {
    1: { name: 'LOX FILL VALVE', short: 'lox_fill', type: 'fill', timer: 30 },
    2: { name: 'FUEL FILL VALVE', short: 'fuel_fill', type: 'fill', timer: 30 },
    3: { name: 'LOX DRAIN VALVE', short: 'lox_drain', type: 'drain', timer: 30 },
    4: { name: 'FUEL DRAIN VALVE', short: 'fuel_drain', type: 'drain', timer: 30 },
    5: { name: 'LOX VENT GROUND', short: 'lox_vent_gse', type: 'vent', timer: 30 },
    6: { name: 'FUEL VENT GROUND', short: 'fuel_vent_gse', type: 'vent', timer: 30 },
    7: { name: 'PRESSURANT SUPPLY', short: 'pressurant', type: 'pressurize', timer: 30 },
    8: { name: 'WATER PUMP', short: 'water_pump', type: 'cooling' },
    9: { name: 'LOX BOILOFF HEATER', short: 'lox_heater', type: 'heating' },
    10: { name: 'TEST VALVE 1', short: 'test1', type: 'test' },
    11: { name: 'TEST VALVE 2', short: 'test2', type: 'test' },
    12: { name: 'QUICK DISCONNECT', short: 'qd', type: 'disconnect' },
    13: { name: 'GSE SPARE 13', short: 'spare13', type: 'spare' },
    14: { name: 'GSE SPARE 14', short: 'spare14', type: 'spare' },
    15: { name: 'GSE SPARE 15', short: 'spare15', type: 'spare' },
    16: { name: 'GSE SPARE 16', short: 'spare16', type: 'spare' },
  };

  const rocketDcMeta = {
    1: { name: 'LOX MAIN VALVE', short: 'lox_main', type: 'run_valve', timer: 30 },
    2: { name: 'FUEL MAIN VALVE', short: 'fuel_main', type: 'run_valve', timer: 30 },
    3: { name: 'IGNITER SOLENOID', short: 'igniter', type: 'ignition' },
    4: { name: 'LOX VENT VALVE', short: 'lox_vent', type: 'vent', timer: 30 },
    5: { name: 'FUEL VENT VALVE', short: 'fuel_vent', type: 'vent', timer: 30 },
    6: { name: 'LOX PRESSURIZATION', short: 'lox_pressurize', type: 'pressurize', timer: 30 },
    7: { name: 'FUEL PRESSURIZATION', short: 'fuel_pressurize', type: 'pressurize', timer: 30 },
    8: { name: 'LOX PURGE', short: 'lox_purge', type: 'purge' },
    9: { name: 'FUEL PURGE', short: 'fuel_purge', type: 'purge' },
    10: { name: 'ENGINE COOLDOWN', short: 'cooldown', type: 'cooling' },
    11: { name: 'RCS THRUSTER 1', short: 'rcs1', type: 'rcs' },
    12: { name: 'RCS THRUSTER 2', short: 'rcs2', type: 'rcs' },
    13: { name: 'ROCKET SPARE 13', short: 'spare13', type: 'spare' },
    14: { name: 'ROCKET SPARE 14', short: 'spare14', type: 'spare' },
    15: { name: 'ROCKET SPARE 15', short: 'spare15', type: 'spare' },
    16: { name: 'ROCKET SPARE 16', short: 'spare16', type: 'spare' },
  };

  let gseDcCfg = { ...gseDcMeta };
  let rocketDcCfg = { ...rocketDcMeta };

  onMount(async () => {
    const host = window.location.hostname || 'localhost';
    const base = `http://${host}:8081/configs`;
    const fetchCfg = async (path) => {
      try {
        const r = await fetch(`${base}/${path}`, { cache: 'no-store' });
        if (!r.ok) return null;
        return await r.json();
      } catch { return null; }
    };
    const [gse, rocket] = await Promise.all([
      fetchCfg('gse_panda_dc.json'),
      fetchCfg('rocket_panda_dc.json'),
    ]);
    const toMeta = (json) => {
      const out = {};
      (json?.channels || []).forEach(c => {
        const d = c.dc; if (!d) return;
        out[d.id] = {
          name: d.name,
          short: d.short_name,
          type: d.type || 'misc',
          timer: d.timer || 0,
        };
      });
      return out;
    };
    if (gse) gseDcCfg = { ...gseDcMeta, ...toMeta(gse) };
    if (rocket) rocketDcCfg = { ...rocketDcMeta, ...toMeta(rocket) };
  });

  $: gseDc = $devices['gse_panda']?.dc || {};
  $: rocketDc = $devices['rocket_panda']?.dc || {};
  $: gseArmed = $devices['gse_panda']?.armed ?? false;
  $: rocketArmed = $devices['rocket_panda']?.armed ?? false;

  function dcChannelList(dcData, meta, deviceId, armed) {
    return Object.entries(dcData).map(([ch, data]) => {
      const m = meta[parseInt(ch)] || { name: `DC${ch}`, short: `dc${ch}`, type: 'misc' };
      return {
        ch: parseInt(ch),
        name: m.name,
        shortName: m.short,
        type: m.type,
        timer: m.timer || 0,
        state: data.state || false,
        current: data.value || 0,
        device: deviceId,
        armed,
      };
    }).sort((a, b) => a.ch - b.ch);
  }

  $: gseDcChannels = dcChannelList(gseDc, gseDcCfg, 'gse_panda', gseArmed);
  $: rocketDcChannels = dcChannelList(rocketDc, rocketDcCfg, 'rocket_panda', rocketArmed);
</script>

<div class="controls-layout">
  <!-- GSE Controls -->
  <div class="dc-section">
    <div class="section-header">
      <span class="section-title">GSE Panda — DC Channels</span>
      <span class="section-count">{gseDcChannels.length} ch</span>
    </div>
    <div class="dc-grid">
      {#each gseDcChannels as ch (ch.ch)}
        <DCChannel
          name={ch.name}
          shortName={ch.shortName}
          channelId={ch.ch}
          device={ch.device}
          type={ch.type}
          state={ch.state}
          current={ch.current}
          armed={ch.armed}
          timer={ch.timer}
        />
      {/each}
    </div>
  </div>

  <!-- Rocket Controls -->
  <div class="dc-section">
    <div class="section-header">
      <span class="section-title">Rocket Panda — DC Channels</span>
      <span class="section-count">{rocketDcChannels.length} ch</span>
    </div>
    <div class="dc-grid">
      {#each rocketDcChannels as ch (ch.ch)}
        <DCChannel
          name={ch.name}
          shortName={ch.shortName}
          channelId={ch.ch}
          device={ch.device}
          type={ch.type}
          state={ch.state}
          current={ch.current}
          armed={ch.armed}
          timer={ch.timer}
        />
      {/each}
    </div>
  </div>
</div>

<style>
  .controls-layout {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 2px;
    background: var(--border-light);
    overflow-y: auto;
  }
  .dc-section {
    background: var(--bg-surface);
    border-radius: var(--radius-sm);
    padding: 10px;
  }
  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-light);
    margin-bottom: 8px;
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
  .dc-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 6px;
  }
</style>
