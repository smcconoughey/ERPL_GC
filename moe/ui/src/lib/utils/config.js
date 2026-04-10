const CONFIG_BASE = '/configs';

let configCache = {};

async function fetchJson(url) {
  try {
    const resp = await fetch(url, { cache: 'no-store' });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } catch (e) {
    console.warn(`Failed to load ${url}:`, e.message);
    return null;
  }
}

export async function loadSystemConfig() {
  // Try to load from the backend HTTP server
  const urls = [
    `http://${window.location.hostname || 'localhost'}:8081/configs/moe_system.json`,
    '/configs/moe_system.json',
  ];

  for (const url of urls) {
    const data = await fetchJson(url);
    if (data) return data;
  }
  return null;
}

export async function loadChannelConfigs() {
  const baseUrl = `http://${window.location.hostname || 'localhost'}:8081/configs`;
  
  const configs = {
    rocket_pt: null,
    rocket_dc: null,
    gse_pt: null,
    gse_dc: null,
  };

  const [rpt, rdc, gpt, gdc] = await Promise.all([
    fetchJson(`${baseUrl}/rocket_pt.json`),
    fetchJson(`${baseUrl}/rocket_dc.json`),
    fetchJson(`${baseUrl}/gse_pt.json`),
    fetchJson(`${baseUrl}/gse_dc.json`),
  ]);

  configs.rocket_pt = rpt;
  configs.rocket_dc = rdc;
  configs.gse_pt = gpt;
  configs.gse_dc = gdc;

  configCache = configs;
  return configs;
}

export function getChannelConfig(deviceId, type, channelId) {
  const key = `${deviceId.replace('_panda', '')}_${type}`;
  const cfg = configCache[key];
  if (!cfg || !cfg.channels) return null;
  const entry = cfg.channels.find(c => c[type] && c[type].id === parseInt(channelId));
  return entry ? entry[type] : null;
}

export function getAllChannels(deviceId, type) {
  const key = `${deviceId.replace('_panda', '')}_${type}`;
  const cfg = configCache[key];
  if (!cfg || !cfg.channels) return [];
  return cfg.channels.map(c => c[type]).filter(Boolean);
}
