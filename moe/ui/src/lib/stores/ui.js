import { writable } from 'svelte/store';

export const activeTab = writable('overview');
export const toasts = writable([]);

let toastId = 0;

export function showToast(title, message, type = 'info') {
  const id = ++toastId;
  toasts.update(t => [...t, { id, title, message, type }]);
  setTimeout(() => {
    toasts.update(t => t.filter(toast => toast.id !== id));
  }, 3500);
}

export const updateRate = writable(0);
export const messageCount = writable(0);

// Track update rate
let lastRateCheck = Date.now();
let rateCounter = 0;

export function tickMessage() {
  rateCounter++;
  messageCount.update(n => n + 1);
  const now = Date.now();
  const elapsed = (now - lastRateCheck) / 1000;
  if (elapsed >= 1) {
    updateRate.set(+(rateCounter / elapsed).toFixed(1));
    rateCounter = 0;
    lastRateCheck = now;
  }
}
