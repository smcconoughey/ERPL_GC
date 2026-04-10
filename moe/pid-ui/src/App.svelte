<script>
  import { onMount } from 'svelte';
  import Header from './lib/components/Header.svelte';
  import InfoBar from './lib/components/InfoBar.svelte';
  import Toast from './lib/components/Toast.svelte';
  import PIDGrid from './lib/components/PIDGrid.svelte';
  import PIDLegend from './lib/components/PIDLegend.svelte';
  import { connectWebSocket, onMessage } from './lib/stores/websocket.js';
  import { devices } from './lib/stores/devices.js';
  import { activeTab, toasts, tickMessage, showToast } from './lib/stores/ui.js';
  import { pidGrid, pidConfig, pidFileName } from './lib/stores/pid.js';
  import { parseXlsx } from './lib/utils/pid-parser.js';
  import { loadConfigMapping } from './lib/utils/config-loader.js';

  let fileInput;
  let dragOver = false;

  onMount(async () => {
    connectWebSocket(3942);
    const unsub = onMessage(() => tickMessage());

    // Load channel configs from moe/configs/ on the backend
    try {
      const mapping = await loadConfigMapping();
      pidConfig.set(mapping);
      console.log(`Loaded ${Object.keys(mapping).length} channel mappings from moe/configs/`);
    } catch (e) {
      console.warn('Could not load configs from backend:', e);
    }

    // Try to auto-load a default layout from public/
    await loadDefaultLayout();

    return () => unsub();
  });

  async function loadDefaultLayout() {
    try {
      const resp = await fetch('/moe_pid_layout.xlsx');
      if (resp.ok) {
        const buf = await resp.arrayBuffer();
        processXlsx(buf, 'moe_pid_layout.xlsx');
      }
    } catch (e) {
      // No default layout, that's fine
    }
  }

  function processXlsx(arrayBuffer, filename) {
    try {
      const result = parseXlsx(arrayBuffer);
      pidGrid.set(result.grid);
      pidFileName.set(filename);
      showToast('Layout Loaded', `${result.rows}x${result.cols} grid from "${result.sheetName}"`, 'success');
      activeTab.set('pid');
    } catch (e) {
      console.error('Failed to parse XLSX:', e);
      showToast('Parse Error', e.message, 'error');
    }
  }

  function handleFileSelect(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    readFile(file);
  }

  function readFile(file) {
    if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
      showToast('Invalid File', 'Please select an .xlsx file', 'warning');
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => processXlsx(e.target.result, file.name);
    reader.readAsArrayBuffer(file);
  }

  function handleDrop(e) {
    e.preventDefault();
    dragOver = false;
    const file = e.dataTransfer?.files?.[0];
    if (file) readFile(file);
  }

  function handleDragOver(e) {
    e.preventDefault();
    dragOver = true;
  }

  function handleDragLeave() {
    dragOver = false;
  }
</script>

<svelte:head>
  <title>MOE P&ID Builder</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" />
  <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
</svelte:head>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  class="app-root"
  on:drop={handleDrop}
  on:dragover={handleDragOver}
  on:dragleave={handleDragLeave}
>
  <Header />
  <InfoBar />

  <main class="main-content">
    {#if $activeTab === 'pid'}
      <PIDGrid />
    {:else if $activeTab === 'legend'}
      <PIDLegend />
    {/if}
  </main>

  <!-- File loader bar -->
  <div class="file-bar">
    <button class="btn-load" on:click={() => fileInput.click()}>
      <i class="fas fa-folder-open"></i> Load XLSX
    </button>
    <input
      bind:this={fileInput}
      type="file"
      accept=".xlsx,.xls"
      on:change={handleFileSelect}
      hidden
    />
    <span class="file-hint">
      <i class="fas fa-info-circle"></i>
      Drag & drop an .xlsx file anywhere, or click Load
    </span>
  </div>

  <!-- Drag overlay -->
  {#if dragOver}
    <div class="drag-overlay">
      <div class="drag-icon">
        <i class="fas fa-file-excel"></i>
        <span>Drop XLSX here</span>
      </div>
    </div>
  {/if}

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
    position: relative;
  }

  .main-content {
    flex: 1;
    display: flex;
    overflow: hidden;
  }

  .file-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 6px 20px;
    background: var(--bg-surface);
    border-top: 1px solid var(--border-light);
    flex-shrink: 0;
  }

  .btn-load {
    padding: 5px 14px;
    background: var(--blue-500);
    color: white;
    border: none;
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: 11px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: var(--font-sans);
    transition: all 0.2s;
    white-space: nowrap;
  }
  .btn-load:hover { background: var(--blue-600); box-shadow: 0 2px 8px rgba(49,130,206,0.3); }

  .file-hint {
    font-size: 11px;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .file-hint i { font-size: 10px; }

  .drag-overlay {
    position: absolute;
    inset: 0;
    background: rgba(49, 130, 206, 0.12);
    border: 3px dashed var(--blue-500);
    z-index: 2000;
    display: flex;
    align-items: center;
    justify-content: center;
    pointer-events: none;
    animation: fadeIn 0.15s ease-out;
  }
  .drag-icon {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    color: var(--blue-500);
    font-size: 16px;
    font-weight: 700;
  }
  .drag-icon i { font-size: 48px; }

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
