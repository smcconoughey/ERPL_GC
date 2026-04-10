<script>
  import DeviceBadge from './DeviceBadge.svelte';
  import { devices } from '../stores/devices.js';
  import { activeTab, showToast } from '../stores/ui.js';
  import { wsConnected, sendCommand } from '../stores/websocket.js';

  const tabs = [
    { id: 'overview', label: 'Overview', icon: 'fa-th-large' },
    { id: 'telemetry', label: 'Telemetry', icon: 'fa-chart-line' },
    { id: 'pid', label: 'P&ID', icon: 'fa-project-diagram' },
    { id: 'controls', label: 'Controls', icon: 'fa-sliders-h' },
  ];

  $: rocketConnected = $devices['rocket_panda']?.connected ?? false;
  $: gseConnected = $devices['gse_panda']?.connected ?? false;
  $: daqConnected = $devices['ni_daq']?.connected ?? false;
  $: anyArmed = ($devices['rocket_panda']?.armed) || ($devices['gse_panda']?.armed);

  function armAll() {
    if (typeof Swal !== 'undefined') {
      Swal.fire({
        title: 'Arm System?',
        html: 'This will enable all control valves.<br><strong>Proceed with caution.</strong>',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#ed8936',
        confirmButtonText: 'ARM',
        cancelButtonText: 'Cancel'
      }).then(result => {
        if (result.isConfirmed) {
          sendCommand({ action: 'arm', device: 'rocket_panda' });
          sendCommand({ action: 'arm', device: 'gse_panda' });
          showToast('Armed', 'System is now armed', 'warning');
        }
      });
    } else {
      sendCommand({ action: 'arm', device: 'rocket_panda' });
      sendCommand({ action: 'arm', device: 'gse_panda' });
      showToast('Armed', 'System is now armed', 'warning');
    }
  }

  function disarmAll() {
    sendCommand({ action: 'disarm', device: 'rocket_panda' });
    sendCommand({ action: 'disarm', device: 'gse_panda' });
    showToast('Disarmed', 'System is disarmed', 'success');
  }

  function abortAll() {
    if (typeof Swal !== 'undefined') {
      Swal.fire({
        title: 'ABORT SEQUENCE?',
        html: '<strong style="color: red;">This will close all run valves immediately.</strong>',
        icon: 'error',
        showCancelButton: true,
        confirmButtonColor: '#e53e3e',
        confirmButtonText: 'CONFIRM ABORT',
        cancelButtonText: 'Cancel'
      }).then(result => {
        if (result.isConfirmed) {
          sendCommand({ action: 'abort' });
          showToast('ABORT', 'Abort sequence initiated', 'error');
        }
      });
    } else {
      sendCommand({ action: 'abort' });
      showToast('ABORT', 'Abort sequence initiated', 'error');
    }
  }

  function emergencyStop() {
    sendCommand({ action: 'estop' });
    showToast('EMERGENCY STOP', 'E-STOP activated — all systems halted', 'error');
  }

  function startLog() {
    sendCommand({ action: 'start_logging' });
    showToast('Logging', 'New log file started', 'success');
  }
</script>

<svelte:window on:keydown={(e) => { if (e.key === 'Escape') emergencyStop(); }} />

<header class:armed={anyArmed}>
  <!-- ABORT button (left edge) -->
  <button class="btn-abort" on:click={abortAll}>ABORT</button>

  <div class="header-center">
    <!-- Title + Device Badges -->
    <div class="title-group">
      <h1 class="title">MOE</h1>
      <div class="badges">
        <DeviceBadge label="ROCKET" connected={rocketConnected} />
        <DeviceBadge label="GSE" connected={gseConnected} />
        <DeviceBadge label="DAQ" connected={daqConnected} />
      </div>
    </div>

    <!-- ARM / DISARM -->
    <div class="arm-group">
      <button class="btn-compact btn-disarm" on:click={disarmAll}>
        <i class="fas fa-shield-alt"></i> DISARM
      </button>
      <button class="btn-compact btn-arm" on:click={armAll}>
        <i class="fas fa-exclamation-triangle"></i> ARM
      </button>
    </div>

    <!-- Tab Navigation -->
    <nav class="tab-nav">
      {#each tabs as tab}
        <button
          class="tab-btn"
          class:active={$activeTab === tab.id}
          on:click={() => activeTab.set(tab.id)}
        >
          <i class="fas {tab.icon}"></i>
          <span>{tab.label}</span>
        </button>
      {/each}
    </nav>

    <!-- Logging -->
    <div class="log-group">
      <div class="log-dot" class:active={false}></div>
      <button class="btn-log" on:click={startLog}>
        <i class="fas fa-circle"></i> LOG
      </button>
    </div>
  </div>

  <!-- E-STOP button (right edge) -->
  <button class="btn-estop" on:click={emergencyStop}>E-STOP</button>
</header>

<style>
  header {
    display: flex;
    align-items: stretch;
    background: linear-gradient(to right, #f5f5f5, #ffffff);
    border-bottom: 2px solid var(--border-light);
    position: relative;
    z-index: 1000;
    flex-shrink: 0;
    height: 52px;
    box-shadow: var(--shadow-sm);
    transition: box-shadow 0.3s ease, background 0.3s ease;
  }
  header.armed {
    box-shadow: 0 0 24px rgba(239, 68, 68, 0.4), inset 0 0 40px rgba(239, 68, 68, 0.08);
    background: linear-gradient(to right, #feecec, #fff);
  }

  .btn-abort {
    width: 120px;
    background: var(--yellow-400);
    color: black;
    font-weight: 800;
    font-size: 16px;
    border: none;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 2px;
    transition: all 0.2s;
    flex-shrink: 0;
    font-family: var(--font-sans);
  }
  .btn-abort:hover { background: #ffed4e; }

  .btn-estop {
    width: 120px;
    background: var(--red-700);
    color: white;
    font-weight: 800;
    font-size: 16px;
    border: none;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 2px;
    transition: all 0.2s;
    flex-shrink: 0;
    font-family: var(--font-sans);
  }
  .btn-estop:hover { background: #b30000; }

  .header-center {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 0 16px;
    overflow: hidden;
  }

  .title-group {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-shrink: 0;
  }
  .title {
    font-size: 22px;
    font-weight: 900;
    color: var(--red-500);
    letter-spacing: 2px;
    margin: 0;
  }
  .badges {
    display: flex;
    gap: 6px;
  }

  .arm-group {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
    padding: 0 12px;
    border-left: 1px solid var(--border-light);
    border-right: 1px solid var(--border-light);
  }
  .btn-compact {
    padding: 8px 14px;
    border: none;
    border-radius: var(--radius-sm);
    font-weight: 700;
    font-size: 11px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    text-transform: uppercase;
    transition: all 0.2s;
    font-family: var(--font-sans);
    letter-spacing: 0.5px;
  }
  .btn-disarm { background: var(--green-600); color: white; }
  .btn-disarm:hover { background: var(--green-700); box-shadow: 0 2px 8px rgba(56,161,105,0.3); }
  .btn-arm { background: var(--orange-500); color: white; }
  .btn-arm:hover { background: var(--orange-600); box-shadow: 0 2px 8px rgba(237,137,54,0.3); }

  .tab-nav {
    display: flex;
    gap: 2px;
    flex: 1;
    justify-content: center;
  }
  .tab-btn {
    padding: 6px 16px;
    background: transparent;
    border: none;
    border-bottom: 3px solid transparent;
    cursor: pointer;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-tertiary);
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
    font-family: var(--font-sans);
    white-space: nowrap;
    height: 100%;
  }
  .tab-btn:hover { color: var(--text-secondary); background: rgba(0,0,0,0.03); }
  .tab-btn.active {
    color: var(--blue-500);
    border-bottom-color: var(--blue-500);
    background: rgba(49,130,206,0.04);
  }

  .log-group {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
    padding-left: 12px;
    border-left: 1px solid var(--border-light);
  }
  .log-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--border-medium);
  }
  .log-dot.active {
    background: var(--red-500);
    animation: pulse 0.6s infinite;
  }
  .btn-log {
    padding: 6px 12px;
    background: var(--green-500);
    color: white;
    border: none;
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: 11px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-family: var(--font-sans);
    transition: all 0.2s;
  }
  .btn-log:hover { background: var(--green-600); }

  @media (max-width: 1100px) {
    .badges { display: none; }
    .tab-btn span { display: none; }
  }
</style>
