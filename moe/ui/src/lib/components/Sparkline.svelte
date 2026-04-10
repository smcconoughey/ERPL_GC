<script>
  import { onMount, afterUpdate } from 'svelte';

  export let data = [];
  export let width = 120;
  export let height = 28;
  export let color = '#16a34a';
  export let fillOpacity = 0.15;

  let canvas;

  function draw() {
    if (!canvas || !data || data.length < 2) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    const len = data.length;
    let min = Infinity, max = -Infinity;
    for (let i = 0; i < len; i++) {
      if (data[i] < min) min = data[i];
      if (data[i] > max) max = data[i];
    }
    const range = max - min || 1;
    const pad = 2;

    // Fill
    ctx.beginPath();
    ctx.moveTo(0, height);
    for (let i = 0; i < len; i++) {
      const x = (i / (len - 1)) * width;
      const y = height - pad - ((data[i] - min) / range) * (height - pad * 2);
      if (i === 0) ctx.lineTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.lineTo(width, height);
    ctx.closePath();
    ctx.fillStyle = color + Math.round(fillOpacity * 255).toString(16).padStart(2, '0');
    ctx.fill();

    // Line
    ctx.beginPath();
    for (let i = 0; i < len; i++) {
      const x = (i / (len - 1)) * width;
      const y = height - pad - ((data[i] - min) / range) * (height - pad * 2);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineJoin = 'round';
    ctx.stroke();

    // Current value dot
    if (len > 0) {
      const lastX = width;
      const lastY = height - pad - ((data[len - 1] - min) / range) * (height - pad * 2);
      ctx.beginPath();
      ctx.arc(lastX - 1, lastY, 2.5, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
    }
  }

  onMount(draw);
  afterUpdate(draw);
</script>

<canvas
  bind:this={canvas}
  style="width: {width}px; height: {height}px;"
  class="sparkline"
></canvas>

<style>
  .sparkline {
    display: block;
    border-radius: 3px;
    image-rendering: crisp-edges;
  }
</style>
