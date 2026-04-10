import { writable, get } from 'svelte/store';

export const wsConnected = writable(false);
export const wsError = writable(null);

let ws = null;
let reconnectTimer = null;
const messageHandlers = new Set();

export function onMessage(handler) {
  messageHandlers.add(handler);
  return () => messageHandlers.delete(handler);
}

export function sendCommand(cmd) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(cmd));
    return true;
  }
  return false;
}

export function connectWebSocket(port = 3942) {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  const host = window.location.hostname || 'localhost';
  const url = `ws://${host}:${port}`;

  try {
    ws = new WebSocket(url);

    ws.onopen = () => {
      wsConnected.set(true);
      wsError.set(null);
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        messageHandlers.forEach(handler => {
          try { handler(msg); } catch (e) { console.error('Message handler error:', e); }
        });
      } catch (e) {
        // Ignore parse errors
      }
    };

    ws.onerror = () => {
      wsConnected.set(false);
      wsError.set('Connection error');
    };

    ws.onclose = () => {
      wsConnected.set(false);
      ws = null;
      reconnectTimer = setTimeout(() => connectWebSocket(port), 3000);
    };
  } catch (e) {
    wsConnected.set(false);
    wsError.set(e.message);
    reconnectTimer = setTimeout(() => connectWebSocket(port), 3000);
  }
}
