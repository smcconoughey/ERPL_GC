import { writable, derived } from 'svelte/store';
import { onMessage } from './websocket.js';

const HISTORY_MAX = 120; // 60 seconds at 2Hz

function createDeviceStore() {
  const { subscribe, set, update } = writable({});

  // PT history buffers: { deviceId: { channelId: [value, ...] } }
  const ptHistory = {};
  const lcHistory = {};
  const tcHistory = {};

  function pushHistory(store, deviceId, ch, value) {
    if (!store[deviceId]) store[deviceId] = {};
    if (!store[deviceId][ch]) store[deviceId][ch] = [];
    store[deviceId][ch].push(value);
    if (store[deviceId][ch].length > HISTORY_MAX) {
      store[deviceId][ch].shift();
    }
  }

  // Listen for data messages from the WebSocket
  onMessage((msg) => {
    if (msg.type !== 'data' || !msg.devices) return;

    update(current => {
      const next = { ...current };

      Object.entries(msg.devices).forEach(([deviceId, data]) => {
        const prev = next[deviceId] || {};
        const device = {
          ...prev,
          device_id: data.device_id || deviceId,
          device_type: data.device_type || prev.device_type || '',
          connected: data.connected ?? prev.connected ?? false,
          armed: data.armed ?? prev.armed ?? false,
          last_update: data.last_update || new Date().toISOString(),
        };

        // PT channels
        if (data.pt && typeof data.pt === 'object') {
          device.pt = { ...(prev.pt || {}) };
          Object.entries(data.pt).forEach(([ch, reading]) => {
            device.pt[ch] = reading;
            if (reading && reading.value !== undefined) {
              pushHistory(ptHistory, deviceId, ch, reading.value);
            }
          });
        }

        // LC channels
        if (data.lc && typeof data.lc === 'object') {
          device.lc = { ...(prev.lc || {}) };
          Object.entries(data.lc).forEach(([ch, reading]) => {
            device.lc[ch] = reading;
            if (reading && reading.value !== undefined) {
              pushHistory(lcHistory, deviceId, ch, reading.value);
            }
          });
        }

        // TC channels
        if (data.tc && typeof data.tc === 'object') {
          device.tc = { ...(prev.tc || {}) };
          Object.entries(data.tc).forEach(([ch, reading]) => {
            device.tc[ch] = reading;
            if (reading && reading.value !== undefined) {
              pushHistory(tcHistory, deviceId, ch, reading.value);
            }
          });
        }

        // DC channels
        if (data.dc && typeof data.dc === 'object') {
          device.dc = { ...(prev.dc || {}) };
          Object.entries(data.dc).forEach(([ch, reading]) => {
            device.dc[ch] = reading;
          });
        }

        next[deviceId] = device;
      });

      return next;
    });
  });

  return {
    subscribe,
    getPtHistory: (deviceId, ch) => (ptHistory[deviceId] && ptHistory[deviceId][ch]) || [],
    getLcHistory: (deviceId, ch) => (lcHistory[deviceId] && lcHistory[deviceId][ch]) || [],
    getTcHistory: (deviceId, ch) => (tcHistory[deviceId] && tcHistory[deviceId][ch]) || [],
  };
}

export const devices = createDeviceStore();

export const rocketPanda = derived(devices, $d => $d['rocket_panda'] || {});
export const gsePanda = derived(devices, $d => $d['gse_panda'] || {});
export const niDaq = derived(devices, $d => $d['ni_daq'] || {});
