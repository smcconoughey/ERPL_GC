<script>
  import Sparkline from './Sparkline.svelte';
  import { formatValue, formatUnits, trendDirection, trendSymbols } from '../utils/format.js';

  export let name = '';
  export let shortName = '';
  export let value = undefined;
  export let units = 'psi';
  export let status = 'offline'; // normal, warning, critical, offline
  export let history = [];
  export let channelId = '';
  export let type = 'pt'; // pt, lc, tc
  // TC-only: flash red when value is above this threshold (line not chilled).
  export let chillThreshold = null;

  $: displayValue = formatValue(value, type === 'pt' ? 1 : type === 'lc' ? 1 : 1);
  $: displayUnits = formatUnits(units);
  $: trend = trendDirection(history);
  $: trendChar = trendSymbols[trend];
  $: notChilled = type === 'tc'
    && chillThreshold !== null && chillThreshold !== undefined
    && typeof value === 'number' && isFinite(value)
    && value > chillThreshold;
  $: sparkColor = (notChilled || status === 'critical') ? '#ef4444' : status === 'warning' ? '#f59e0b' : '#16a34a';
</script>

<div class="sensor-card {status}" class:not-chilled={notChilled}>
  <div class="sensor-left">
    <div class="sensor-name">{name}</div>
    <div class="sensor-short">{shortName || type.toUpperCase() + channelId}</div>
    <div class="spark-container">
      <Sparkline data={history} width={100} height={24} color={sparkColor} />
    </div>
  </div>
  <div class="sensor-right">
    <div class="sensor-value-row">
      <span class="value">{displayValue}</span>
      <span class="units">{displayUnits}</span>
      <span class="trend {trend}">{trendChar}</span>
    </div>
    {#if notChilled}
      <div class="chill-badge" title="TC is above chill threshold ({chillThreshold} {displayUnits})">
        NOT CHILLED &gt; {chillThreshold}{displayUnits}
      </div>
    {/if}
  </div>
</div>

<style>
  .sensor-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 10px;
    background: var(--bg-elevated);
    border-radius: var(--radius-sm);
    border-left: 3px solid var(--sensor-offline);
    transition: all 0.2s ease;
    gap: 8px;
    min-height: 52px;
  }
  .sensor-card.normal  { border-left-color: var(--sensor-normal); }
  .sensor-card.warning { border-left-color: var(--sensor-warning); background: #fff7ed; }
  .sensor-card.critical { border-left-color: var(--sensor-critical); background: #fef2f2; }
  .sensor-card.not-chilled {
    border-left-color: #dc2626;
    background: #fef2f2;
    animation: chillFlash 0.9s ease-in-out infinite;
  }
  @keyframes chillFlash {
    0%, 100% { background: #fef2f2; }
    50%      { background: #fecaca; }
  }
  .chill-badge {
    font-size: 8px;
    font-weight: 800;
    color: #fff;
    background: #dc2626;
    padding: 1px 5px;
    border-radius: 3px;
    margin-top: 3px;
    letter-spacing: 0.3px;
    display: inline-block;
    white-space: nowrap;
  }

  .sensor-left {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .sensor-name {
    font-size: 10px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.3px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .sensor-short {
    font-size: 9px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }
  .spark-container {
    margin-top: 2px;
  }

  .sensor-right {
    flex-shrink: 0;
    text-align: right;
  }
  .sensor-value-row {
    display: flex;
    align-items: baseline;
    gap: 3px;
    justify-content: flex-end;
  }
  .value {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
    font-family: var(--font-mono);
    letter-spacing: -0.5px;
  }
  .units {
    font-size: 10px;
    color: var(--text-tertiary);
    font-weight: 500;
  }
  .trend {
    font-size: 12px;
    margin-left: 2px;
  }
  .trend.up { color: var(--green-600); }
  .trend.down { color: var(--red-500); }
  .trend.flat { color: var(--text-muted); }
</style>
