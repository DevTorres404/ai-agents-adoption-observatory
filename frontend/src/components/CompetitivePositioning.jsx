import { useMemo, useState } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, ReferenceLine,
  ReferenceArea, ResponsiveContainer, Tooltip } from 'recharts';
import { QUADRANTS, positioningData, projectScore, restoreScore } from '../utils/positioning';
import './CompetitivePositioning.css';

const format = value => new Intl.NumberFormat('es-EC', { maximumFractionDigits: 2 }).format(value);
const compact = value => new Intl.NumberFormat('es-EC', { notation: 'compact', maximumFractionDigits: 1 }).format(value);

function PointDetails({ point }) {
  return <>
    <strong>{point.nombre_agente}</strong>
    <span style={{ color: point.quadrant.color }}>{point.quadrant.label}</span>
    <dl><div><dt>Adopción</dt><dd>{format(point.adopcion)}</dd></div>
      <div><dt>Popularidad</dt><dd>{format(point.popularidad)}</dd></div>
      <div><dt>Observaciones</dt><dd>{format(point.total_observaciones)}</dd></div></dl>
  </>;
}

function PointTooltip({ active, payload }) {
  const point = payload?.[0]?.payload;
  return active && point ? <div className="positioning-tooltip"><PointDetails point={point} /></div> : null;
}

export default function CompetitivePositioning({ data }) {
  const [scale, setScale] = useState('log');
  const [selectedName, setSelectedName] = useState(null);
  const { points, medAdop, medPop, xAxis, yAxis, omitted } = useMemo(() => positioningData(data, scale), [data, scale]);
  const selected = points.find(point => point.nombre_agente === selectedName);
  const mx = projectScore(medAdop, scale), my = projectScore(medPop, scale);
  const tick = value => compact(restoreScore(value, scale));
  const shape = ({ cx, cy, payload }, highlighted = false) => {
    if (!Number.isFinite(cx) || !Number.isFinite(cy)) return null;
    return <g className="positioning-marker" onClick={() => setSelectedName(payload.nombre_agente)}
      style={{ opacity: selected && !highlighted && selectedName !== payload.nombre_agente ? .4 : 1 }}>
      <title>{`${payload.nombre_agente}: adopción ${format(payload.adopcion)}, popularidad ${format(payload.popularidad)}`}</title>
      {highlighted && <circle cx={cx} cy={cy} r={payload.radius + 5} fill="none" stroke="var(--text-primary)" strokeWidth={2} />}
      <circle cx={cx} cy={cy} r={payload.radius} fill={payload.quadrant.color} stroke="var(--bg-card)" strokeWidth={2} />
      <text x={cx} y={cy} dy=".35em" textAnchor="middle" fill="#fff" fontSize={11} fontWeight={800} pointerEvents="none">{payload.marker}</text>
      {highlighted && <text x={cx + (payload.x > xAxis.domain[1] / 2 ? -20 : 20)} y={cy - 22}
        textAnchor={payload.x > xAxis.domain[1] / 2 ? 'end' : 'start'} className="positioning-point-label">{payload.nombre_agente}</text>}
    </g>;
  };
  const zones = [
    [mx, xAxis.domain[1], my, yAxis.domain[1], 0],
    [xAxis.domain[0], mx, my, yAxis.domain[1], 1],
    [mx, xAxis.domain[1], yAxis.domain[0], my, 2],
    [xAxis.domain[0], mx, yAxis.domain[0], my, 3],
  ];

  return <section className="panel panel-featured exec-quadrant-panel positioning-panel" aria-labelledby="positioning-title">
    <div className="positioning-header">
      <div><h2 id="positioning-title">Mapa de Posicionamiento Competitivo</h2>
        <p className="chart-description">Compara adopción y popularidad. Selecciona un agente para destacar su posición y ver sus valores.</p></div>
      <div className="positioning-scale" role="group" aria-label="Escala del mapa">
        <button type="button" aria-pressed={scale === 'log'} onClick={() => setScale('log')}>Logarítmica</button>
        <button type="button" aria-pressed={scale === 'linear'} onClick={() => setScale('linear')}>Lineal</button>
      </div>
    </div>
    {points.length === 0 ? <div className="positioning-empty">Sin datos válidos para el período seleccionado.</div> : <>
      <div className="positioning-legend" aria-label="Cuadrantes de posicionamiento">
        {QUADRANTS.map(q => <div key={q.label} title={q.desc}><i style={{ background: q.color }} /><strong>{q.label}</strong><span>{q.desc}</span></div>)}
      </div>
      <div className="positioning-chart" role="img" aria-label="Dispersión de adopción y popularidad. Los valores exactos están disponibles en la lista de agentes inferior.">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 34, right: 30, bottom: 30, left: 16 }}>
            <CartesianGrid strokeDasharray="3 5" stroke="var(--border-primary)" />
            <XAxis type="number" dataKey="x" name="Adopción" domain={xAxis.domain} ticks={xAxis.ticks} tickFormatter={tick}
              tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} tickLine={false}
              label={{ value: 'Score de adopción →', position: 'insideBottom', offset: -18, fill: 'var(--text-secondary)', fontSize: 12 }} />
            <YAxis type="number" dataKey="y" name="Popularidad" domain={yAxis.domain} ticks={yAxis.ticks} tickFormatter={tick}
              width={76} tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} tickLine={false}
              label={{ value: 'Popularidad →', angle: -90, position: 'insideLeft', offset: -4, fill: 'var(--text-secondary)', fontSize: 12 }} />
            {zones.map(([x1, x2, y1, y2, index]) => <ReferenceArea key={index} x1={x1} x2={x2} y1={y1} y2={y2}
              fill={QUADRANTS[index].color} fillOpacity={.055} strokeOpacity={0} />)}
            <ReferenceLine x={mx} stroke="var(--text-secondary)" strokeDasharray="5 5" />
            <ReferenceLine y={my} stroke="var(--text-secondary)" strokeDasharray="5 5" />
            <Tooltip content={<PointTooltip />} />
            <Scatter data={selected ? points.filter(point => point.nombre_agente !== selectedName) : points} shape={props => shape(props)} isAnimationActive={false} />
            {selected && <Scatter data={[selected]} shape={props => shape(props, true)} isAnimationActive={false} />}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <div className="positioning-caption">
        <span>Líneas discontinuas: medianas de adopción <b>{format(medAdop)}</b> y popularidad <b>{format(medPop)}</b>.</span>
        <span>{scale === 'log' ? 'Escala log₁₀(1 + valor): conserva los ceros y separa órdenes de magnitud.' : 'Escala lineal: distancias proporcionales a los valores.'} Tamaño del punto: volumen de observaciones.</span>
      </div>
      <div className="positioning-selection" aria-live="polite">
        {selected ? <><div className="positioning-detail"><PointDetails point={selected} /></div>
          <button type="button" onClick={() => setSelectedName(null)}>Quitar selección</button></>
          : <span>Los puntos cercanos pueden superponerse. Elige un nombre abajo para verlo en primer plano.</span>}
      </div>
      <div className="positioning-agents" role="group" aria-label="Seleccionar agente en el mapa">
        {points.map(point => <button type="button" key={point.nombre_agente} aria-pressed={selectedName === point.nombre_agente}
          onClick={() => setSelectedName(point.nombre_agente)}>
          <span className="positioning-number" style={{ background: point.quadrant.color }}>{point.marker}</span>
          <span><strong>{point.nombre_agente}</strong><small>{point.quadrant.label} · {compact(point.total_observaciones)} observaciones</small></span>
        </button>)}
      </div>
      <details className="positioning-method"><summary>Cómo interpretar los indicadores</summary>
        <p>Adopción es la suma de contribuciones observadas normalizadas por fuente; no es un porcentaje ni una escala fija de 0 a 100.
          Popularidad es visibilidad relativa acumulada. Los cuadrantes comparan cada agente con las medianas del conjunto filtrado,
          no con todo el mercado. La escala solo cambia la visualización, no los valores ni su clasificación.</p>
      </details>
    </>}
    {omitted > 0 && <p className="positioning-caption">{omitted} registros sin ambos scores válidos no se representan.</p>}
  </section>;
}
