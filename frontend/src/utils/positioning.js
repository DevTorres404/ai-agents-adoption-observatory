export const QUADRANTS = [
  { label: 'Líderes', color: 'var(--success)', desc: 'Adopción y popularidad altas' },
  { label: 'Retadores', color: 'var(--primary)', desc: 'Mayor popularidad, menor adopción' },
  { label: 'Especializados', color: 'var(--warning)', desc: 'Mayor adopción, menor popularidad' },
  { label: 'Emergentes', color: 'var(--accent)', desc: 'Ambas por debajo de la mediana' },
];

export function median(values) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

export const projectScore = (value, scale) => scale === 'log' ? Math.log10(1 + value) : value;
export const restoreScore = (value, scale) => scale === 'log' ? Math.max(0, 10 ** value - 1) : Math.max(0, value);

export function positioningData(data, scale = 'log') {
  const finiteScore = value => (typeof value === 'number' || typeof value === 'string') && String(value).trim() !== ''
    && Number.isFinite(Number(value)) && Number(value) >= 0;
  const valid = (Array.isArray(data) ? data : [])
    .filter(item => item.nombre_agente && finiteScore(item.adopcion) && finiteScore(item.popularidad))
    .map(item => ({ ...item, adopcion: Number(item.adopcion), popularidad: Number(item.popularidad),
      total_observaciones: Number.isFinite(Number(item.total_observaciones)) ? Math.max(0, Number(item.total_observaciones)) : 0 }))
    .sort((a, b) => b.adopcion - a.adopcion || a.nombre_agente.localeCompare(b.nombre_agente));
  const medAdop = median(valid.map(item => item.adopcion));
  const medPop = median(valid.map(item => item.popularidad));
  const maxVolume = Math.max(1, ...valid.map(item => Math.log1p(item.total_observaciones)));
  const points = valid.map((item, index) => {
    const highA = item.adopcion >= medAdop;
    const highP = item.popularidad >= medPop;
    return { ...item, marker: index + 1, x: projectScore(item.adopcion, scale), y: projectScore(item.popularidad, scale),
      radius: 9 + 5 * Math.log1p(item.total_observaciones) / maxVolume,
      quadrant: QUADRANTS[highA ? (highP ? 0 : 2) : (highP ? 1 : 3)] };
  });
  const axis = key => {
    const maximum = Math.max(1, ...points.map(item => item[key]));
    return { domain: [-maximum * .06, maximum * 1.12], ticks: Array.from({ length: 5 }, (_, i) => maximum * i / 4) };
  };
  return { points, medAdop, medPop, xAxis: axis('x'), yAxis: axis('y'),
    omitted: (Array.isArray(data) ? data.length : 0) - valid.length };
}
