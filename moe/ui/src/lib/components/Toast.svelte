<script>
  export let title = '';
  export let message = '';
  export let type = 'info'; // info, success, warning, error
</script>

<div class="toast {type}" role="alert">
  <div class="toast-icon">
    {#if type === 'success'}
      <i class="fas fa-check-circle"></i>
    {:else if type === 'warning'}
      <i class="fas fa-exclamation-triangle"></i>
    {:else if type === 'error'}
      <i class="fas fa-times-circle"></i>
    {:else}
      <i class="fas fa-info-circle"></i>
    {/if}
  </div>
  <div class="toast-content">
    <div class="toast-title">{title}</div>
    {#if message}
      <div class="toast-message">{message}</div>
    {/if}
  </div>
</div>

<style>
  .toast {
    background: var(--bg-surface);
    padding: 12px 16px;
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-md);
    display: flex;
    align-items: center;
    gap: 12px;
    animation: slideIn 0.2s ease-out;
    border-left: 4px solid var(--blue-500);
    min-width: 260px;
    max-width: 380px;
    pointer-events: auto;
  }
  .toast.warning { border-left-color: var(--orange-500); }
  .toast.success { border-left-color: var(--green-600); }
  .toast.error   { border-left-color: var(--red-500); }

  .toast-icon { font-size: 20px; display: flex; align-items: center; flex-shrink: 0; }
  .toast.warning .toast-icon { color: var(--orange-500); }
  .toast.success .toast-icon { color: var(--green-600); }
  .toast.error   .toast-icon { color: var(--red-500); }
  .toast.info    .toast-icon { color: var(--blue-500); }

  .toast-content { flex: 1; min-width: 0; }
  .toast-title { font-weight: 600; font-size: 13px; color: var(--text-primary); }
  .toast-message { font-size: 12px; color: var(--text-tertiary); margin-top: 2px; }
</style>
