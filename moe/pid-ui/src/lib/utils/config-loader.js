/**
 * Loads channel configs from the MOE backend (moe/configs/) and builds
 * the element-ID → device/channel mapping the PID grid needs for live data.
 *
 * Element IDs in the XLSX (PT1, PB3, LC1, …) are matched against the
 * config channel id + short_name so the grid can look up live values.
 */

const BASE = () => `http://${window.location.hostname || 'localhost'}:8081/configs`;

async function fetchJson(url) {
  try {
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}

/**
 * Build the mapping object:
 *   { 'PT1': { device, type, channel, units, name }, … }
 *
 * Rules for matching an XLSX element ID like "PT5" to a config entry:
 *   - PT<n>  → pt channel id=n         (rocket first, then gse)
 *   - PI<n>  → pt channel whose short_name starts with "pi_"  (injector PTs)
 *   - PV<n>  → pt channel whose short_name starts with "pv_"  (vent PTs)
 *   - TC<n>  → tc channel id=n
 *   - LC<n>  → lc channel id=n
 *   - PB<n>  → dc channel id=n         (rocket first, then gse)
 *   - SV<n>  → dc channel id=n         (alias for solenoid)
 *   - S<n>   → dc channel id=n
 */
export async function loadConfigMapping() {
  const base = BASE();

  const [rocketPt, rocketDc, gsePt, gseDc] = await Promise.all([
    fetchJson(`${base}/rocket_pt.json`),
    fetchJson(`${base}/rocket_dc.json`),
    fetchJson(`${base}/gse_pt.json`),
    fetchJson(`${base}/gse_dc.json`),
  ]);

  const mapping = {};

  // ── Helper: register a channel ────────────────────────────────────
  function addChannel(elemId, device, type, channel) {
    const key = elemId.toUpperCase();
    if (mapping[key]) return;  // first match wins (rocket > gse)
    mapping[key] = { device, type, channel: String(channel.id), units: channel.units || '', name: channel.name || '' };
  }

  // ── PT channels (pressure transducers) ────────────────────────────
  function processPt(cfg, device) {
    if (!cfg?.channels) return;
    for (const entry of cfg.channels) {
      const ch = entry.pt;
      if (!ch) continue;
      const sn = (ch.short_name || '').toLowerCase();

      // Always register as PT<id>
      addChannel(`PT${ch.id}`, device, 'pt', ch);

      // Also register by prefix pattern for injector/vent PTs
      if (sn.startsWith('pi_')) {
        // e.g. pi_lox → PI<id>
        addChannel(`PI${ch.id}`, device, 'pt', ch);
      }
      if (sn.startsWith('pv_')) {
        addChannel(`PV${ch.id}`, device, 'pt', ch);
      }
    }
  }

  // ── DC channels (valves) ──────────────────────────────────────────
  function processDc(cfg, device) {
    if (!cfg?.channels) return;
    for (const entry of cfg.channels) {
      const ch = entry.dc;
      if (!ch) continue;
      addChannel(`PB${ch.id}`, device, 'dc', ch);
      addChannel(`SV${ch.id}`, device, 'dc', ch);
      addChannel(`S${ch.id}`, device, 'dc', ch);
    }
  }

  // Rocket configs take priority (registered first)
  processPt(rocketPt, 'rocket_panda');
  processDc(rocketDc, 'rocket_panda');
  processPt(gsePt, 'gse_panda');
  processDc(gseDc, 'gse_panda');

  // We don't have separate tc/lc config files yet, but if channels come
  // through the websocket they'll be on rocket_panda by convention.
  // Register TC1-16 and LC1-16 as fallbacks.
  for (let i = 1; i <= 16; i++) {
    addChannel(`TC${i}`, 'rocket_panda', 'tc', { id: i, units: 'degF', name: `TC${i}` });
    addChannel(`LC${i}`, 'rocket_panda', 'lc', { id: i, units: 'lbf', name: `LC${i}` });
  }

  return mapping;
}
