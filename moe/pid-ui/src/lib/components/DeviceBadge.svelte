<script>
  export let label = '';
  export let connected = false;
</script>

<div class="badge" class:connected>
  <span class="dot"></span>
  <span class="label">{label}</span>
</div>

<style>
  .badge {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    background: #f0f0f0;
    border-radius: var(--radius-sm);
    font-size: 11px;
    font-weight: 700;
    color: var(--text-secondary);
    border: 1px solid var(--border-light);
    letter-spacing: 0.5px;
    transition: all 0.3s ease;
    user-select: none;
  }
  .badge.connected {
    background: #f0fff4;
    border-color: var(--green-600);
    color: #22543d;
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--red-500);
    flex-shrink: 0;
    transition: all 0.3s ease;
  }
  .badge.connected .dot {
    background: var(--green-600);
    box-shadow: 0 0 6px var(--green-600);
  }
</style>
