<script>
  import { onMount } from 'svelte';
  import Header from './lib/components/Header.svelte';
  import InfoBar from './lib/components/InfoBar.svelte';
  import Toast from './lib/components/Toast.svelte';
  import OverviewView from './lib/views/OverviewView.svelte';
  import TelemetryView from './lib/views/TelemetryView.svelte';
  import PIDView from './lib/views/PIDView.svelte';
  import ControlView from './lib/views/ControlView.svelte';
  import { connectWebSocket, onMessage } from './lib/stores/websocket.js';
  import { devices } from './lib/stores/devices.js';
  import { activeTab, toasts, tickMessage } from './lib/stores/ui.js';

  onMount(() => {
    // Connect WebSocket
    connectWebSocket(3942);

    // Track message rate
    const unsub = onMessage(() => {
      tickMessage();
    });

    return () => unsub();
  });
</script>

<svelte:head>
  <title>MOE Ground Control</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" />
  <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
</svelte:head>

<div class="app-root">
  <Header />
  <InfoBar />

  <main class="main-content">
    {#if $activeTab === 'overview'}
      <OverviewView />
    {:else if $activeTab === 'telemetry'}
      <TelemetryView />
    {:else if $activeTab === 'pid'}
      <PIDView />
    {:else if $activeTab === 'controls'}
      <ControlView />
    {/if}
  </main>

  <!-- Toast Container -->
  <div class="toast-container">
    {#each $toasts as toast (toast.id)}
      <Toast title={toast.title} message={toast.message} type={toast.type} />
    {/each}
  </div>
</div>

<style>
  .app-root {
    display: flex;
    flex-direction: column;
    height: 100%;
    width: 100%;
    overflow: hidden;
  }

  .main-content {
    flex: 1;
    display: flex;
    overflow: hidden;
  }

  .toast-container {
    position: fixed;
    top: 110px;
    right: 20px;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 8px;
    pointer-events: none;
  }
</style>
