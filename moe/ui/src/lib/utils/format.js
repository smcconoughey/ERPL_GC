export function formatValue(value, decimals = 1) {
  if (value === undefined || value === null || !Number.isFinite(value)) return '--';
  return value.toFixed(decimals);
}

export function formatUnits(units) {
  const map = {
    'psi': 'psi',
    'lbf': 'lbf',
    'degF': '°F',
    'degC': '°C',
    'A': 'A',
    'V': 'V',
  };
  return map[units] || units || '';
}

export function sensorStatus(value, config) {
  if (value === undefined || value === null || !Number.isFinite(value)) return 'offline';
  if (!config || !config.range) return 'normal';
  const [min, max] = config.range;
  const warningMargin = (max - min) * 0.1;
  if (value >= max || value <= min) return 'critical';
  if (value >= max - warningMargin || value <= min + warningMargin) return 'warning';
  return 'normal';
}

export function trendDirection(history) {
  if (!history || history.length < 3) return 'flat';
  const recent = history.slice(-5);
  const first = recent[0];
  const last = recent[recent.length - 1];
  const delta = last - first;
  if (Math.abs(delta) < 0.5) return 'flat';
  return delta > 0 ? 'up' : 'down';
}

export const trendSymbols = { up: '↑', down: '↓', flat: '→' };
