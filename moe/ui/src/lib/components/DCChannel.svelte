<script>
  import { onDestroy } from 'svelte';
  import { sendCommand } from '../stores/websocket.js';
  import { showToast } from '../stores/ui.js';

  export let name = '';
  export let shortName = '';
  export let channelId = 1;
  export let device = '';
  export let type = 'misc';
  export let state = false;
  export let current = 0;
  export let armed = false;
  // Minutes before the energized timer flashes red. 0/undefined = no timer shown.
  export let timer = 0;

  let energizedAt = 0;
  let elapsedSec = 0;
  let tick;

  $: if (state) {
    if (!energizedAt) {
      energizedAt = Date.now();
      startTick();
    }
  } else {
    stopTick();
    energizedAt = 0;
    elapsedSec = 0;
  }

  function startTick() {
    if (tick) return;
    tick = setInterval(() => {
      elapsedSec = Math.floor((Date.now() - energizedAt) / 1000);
    }, 500);
    elapsedSec = 0;
  }

  function stopTick() {
    if (tick) {
      clearInterval(tick);
      tick = null;
    }
  }

  onDestroy(stopTick);

  $: ratingSec = (timer || 0) * 60;
  $: overLimit = ratingSec > 0 && elapsedSec >= ratingSec;

  function fmt(s) {
    const m = Math.floor(s / 60);
    const r = s % 60;
    return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`;
  }

  function toggle() {
    if (!armed) {
      showToast('System Not Armed', 'Arm the system before actuating valves', 'warning');
      return;
    }
    const newState = state ? 0 : 1;
    sendCommand({
      action: 'send',
      device: device,
      command: `s${channelId}${newState}.00000`
    });
    showToast('Valve Actuated', `${name}: ${newState ? 'OPEN' : 'CLOSED'}`, newState ? 'success' : 'warning');
  }
</script>

<button class="dc-card {state ? 'active' : 'inactive'} dc-type-{type.toLowerCase()}" on:click={toggle}>
  <div class="dc-header">
    <div class="dc-info">
      <div class="dc-name">{name}</div>
      <div class="dc-short">{shortName} · {type.toUpperCase()}</div>
    </div>
    <span class="dc-pill" class:on={state} class:off={!state}>
      {state ? 'ON' : 'OFF'}
    </span>
  </div>
  <div class="dc-footer">
    {#if timer > 0}
      <span class="dc-timer" class:running={state} class:over={overLimit}>
        <i class="fa-regular fa-clock" aria-hidden="true"></i>
        {state ? fmt(elapsedSec) : '--:--'}
        <span class="dc-rating">/ {timer}m</span>
      </span>
    {:else}
      <span class="dc-timer-placeholder"></span>
    {/if}
    <span class="dc-current">{current.toFixed(3)} A</span>
  </div>
</button>

<style>
  .dc-card {
    background: var(--bg-elevated);
    border: 2px solid var(--border-light);
    border-radius: var(--radius-md);
    padding: 10px;
    cursor: pointer;
    user-select: none;
    transition: all 0.2s ease;
    text-align: left;
    width: 100%;
    font-family: inherit;
  }
  .dc-card:hover {
    border-color: var(--blue-500);
    box-shadow: 0 4px 12px rgba(49, 130, 206, 0.12);
  }
  .dc-card.active {
    border-color: var(--green-600);
    background: #f0fff4;
  }
  .dc-card.inactive {
    border-color: var(--red-500);
    background: #fff5f5;
  }

  .dc-type-fuel { background-color: #fff4e6; border-color: var(--orange-400); }
  .dc-type-lox  { background-color: #e6f4ff; border-color: var(--blue-400); }
  .dc-type-fill { background-color: #e6f4ff; border-color: var(--blue-400); }
  .dc-type-vent { background-color: #f0f4f8; border-color: var(--text-muted); }
  .dc-type-drain { background-color: #fef3f2; border-color: var(--red-500); }
  .dc-type-pressurize { background-color: #e8fff0; border-color: var(--green-400); }

  .dc-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
  }
  .dc-info { min-width: 0; }
  .dc-name {
    font-weight: 700;
    font-size: 12px;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .dc-short {
    font-size: 9px;
    color: var(--text-tertiary);
    text-transform: uppercase;
    margin-top: 2px;
  }
  .dc-pill {
    padding: 3px 10px;
    border-radius: 12px;
    font-weight: 700;
    font-size: 11px;
    flex-shrink: 0;
  }
  .dc-pill.on  { background: var(--green-600); color: white; }
  .dc-pill.off { background: var(--red-500); color: white; }

  .dc-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 6px;
    gap: 8px;
  }
  .dc-current {
    font-size: 10px;
    color: var(--text-tertiary);
    font-family: var(--font-mono);
    text-align: right;
  }
  .dc-timer {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    padding: 2px 6px;
    border-radius: 10px;
    background: rgba(0, 0, 0, 0.04);
  }
  .dc-timer.running {
    color: var(--text-primary);
    background: rgba(49, 130, 206, 0.12);
  }
  .dc-timer .dc-rating {
    color: var(--text-tertiary);
    font-size: 9px;
  }
  .dc-timer.over {
    color: #fff;
    background: #e53e3e;
    animation: dcTimerFlash 0.8s ease-in-out infinite;
  }
  @keyframes dcTimerFlash {
    0%, 100% { background: #e53e3e; box-shadow: 0 0 0 0 rgba(229, 62, 62, 0.55); }
    50%      { background: #b91c1c; box-shadow: 0 0 0 4px rgba(229, 62, 62, 0.0); }
  }
  .dc-timer-placeholder { flex: 1; }
</style>
