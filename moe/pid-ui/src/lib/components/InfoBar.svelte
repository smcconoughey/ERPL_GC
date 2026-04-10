<script>
  import { wsConnected } from '../stores/websocket.js';
  import { updateRate } from '../stores/ui.js';
  import { sendCommand } from '../stores/websocket.js';
  import { showToast } from '../stores/ui.js';

  let clock = '';
  $: {
    const interval = setInterval(() => {
      clock = new Date().toLocaleTimeString();
    }, 1000);
  }

  function allOff() {
    sendCommand({ action: 'estop' });
    showToast('All OFF', 'Commanding all valves closed', 'warning');
  }
</script>

<div class="info-bar">
  <div class="info-left">
    <div class="info-item">
      <i class="fas fa-clock"></i>
      <span>{clock || '--:--:--'}</span>
    </div>
    <div class="info-item">
      <i class="fas fa-heartbeat"></i>
      <span>{$updateRate} Hz</span>
    </div>
    <div class="info-item">
      <span class="status-pill" class:online={$wsConnected} class:offline={!$wsConnected}>
        <i class="fas fa-circle"></i>
        {$wsConnected ? 'Connected' : 'Offline'}
      </span>
    </div>
  </div>
  <div class="info-right">
    <button class="btn-all-off" on:click={allOff}>
      <i class="fas fa-power-off"></i> ALL OFF
    </button>
  </div>
</div>

<style>
  .info-bar {
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border-light);
    padding: 6px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 11px;
    color: var(--text-secondary);
    flex-shrink: 0;
  }
  .info-left, .info-right {
    display: flex;
    gap: 16px;
    align-items: center;
  }
  .info-item {
    display: flex;
    align-items: center;
    gap: 5px;
    white-space: nowrap;
  }
  .info-item i { font-size: 10px; color: var(--text-muted); }

  .status-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 10px;
    font-weight: 600;
  }
  .status-pill i { font-size: 6px; }
  .status-pill.online { background: #d4edda; color: var(--green-600); }
  .status-pill.offline { background: #f8d7da; color: var(--red-500); }

  .btn-all-off {
    padding: 5px 12px;
    background: var(--red-500);
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
  .btn-all-off:hover { background: var(--red-600); box-shadow: 0 2px 8px rgba(229,62,62,0.3); }
</style>
