import React, { useMemo } from 'react';
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid,
  Tooltip as RechartsTooltip, ReferenceLine, ResponsiveContainer,
  BarChart, Bar, Cell, Label
} from 'recharts';
import { TrendingUp, TrendingDown, Zap, Award, Target, BarChart2, Star } from 'lucide-react';

// ─── helpers ────────────────────────────────────────────────────────────────

const toNum = v => { const n = Number(v); return Number.isFinite(n) ? n : 0; };

const fmt = (v, opts = {}) =>
  toNum(v).toLocaleString('es-EC', { maximumFractionDigits: 1, ...opts });

const fmtCompact = v =>
  new Intl.NumberFormat('es-EC', { notation: 'compact', maximumFractionDigits: 1 }).format(toNum(v));

const pct = (a, b) => (b === 0 ? null : ((a - b) / b) * 100);

// ─── Derived metrics from ranking + tendencia ───────────────────────────────

function deriveMetrics(ranking, tendencia) {
  const sorted = [...(ranking || [])].sort((a, b) => toNum(b.adopcion) - toNum(a.adopcion));
  const leader = sorted[0] || null;
  const runner = sorted[1] || null;
  const leaderGap = leader && runner
    ? ((toNum(leader.adopcion) - toNum(runner.adopcion)) / Math.max(toNum(runner.adopcion), 1)) * 100
    : null;

  const sortedTrend = [...(tendencia || [])].sort(
    (a, b) => toNum(a.anio) - toNum(b.anio) || toNum(a.mes) - toNum(b.mes)
  );
  const lastTwo = sortedTrend.slice(-2);
  const momGrowth = lastTwo.length === 2
    ? pct(toNum(lastTwo[1].suma_adopcion), toNum(lastTwo[0].suma_adopcion))
    : null;

  const withIntensity = sorted
    .filter(a => toNum(a.total_observaciones) > 0)
    .map(a => ({ ...a, intensity: toNum(a.adopcion) / toNum(a.total_observaciones) }))
    .sort((a, b) => b.intensity - a.intensity);
  const emergent = withIntensity[0] || null;

  return { sorted, leader, runner, leaderGap, momGrowth, emergent };
}

// ─── Narrative generator ────────────────────────────────────────────────────

function buildNarrative({ leader, runner, leaderGap, momGrowth, emergent, sorted }) {
  if (!leader) return 'No hay suficientes datos para generar un análisis ejecutivo.';

  const parts = [];

  parts.push(
    `${leader.nombre_agente} lidera el mercado con un score de adopción de ${fmtCompact(leader.adopcion)}`
  );

  if (runner && leaderGap !== null) {
    const gapStr = leaderGap >= 100
      ? `${fmt(leaderGap / 100, { maximumFractionDigits: 1 })}× por encima de`
      : `${fmt(leaderGap)}% por encima de`;
    parts[0] += `, ${gapStr} ${runner.nombre_agente} (#2).`;
  } else {
    parts[0] += '.';
  }

  if (momGrowth !== null) {
    const dir = momGrowth >= 0 ? 'crecimiento' : 'retroceso';
    const sign = momGrowth >= 0 ? '+' : '';
    parts.push(
      `El mercado muestra un ${dir} de ${sign}${fmt(momGrowth)}% en adopción total mes a mes.`
    );
  }

  if (emergent && emergent.nombre_agente !== leader.nombre_agente) {
    parts.push(
      `${emergent.nombre_agente} destaca como el agente con mayor intensidad de señal por observación, indicador de adopción concentrada.`
    );
  }

  if (sorted.length >= 4) {
    const topFour = sorted.slice(0, 4).map(a => a.nombre_agente).join(', ');
    parts.push(`El top 4 —${topFour}— concentra la mayor parte del volumen de señal analizado.`);
  }

  return parts.join(' ');
}

// ─── Quadrant helper ────────────────────────────────────────────────────────

function quadrantMeta(adopcion, popularidad, medAdop, medPop) {
  const high_a = adopcion >= medAdop;
  const high_p = popularidad >= medPop;
  if (high_a && high_p) return { label: 'Líderes', color: '#16a36a' };
  if (!high_a && high_p) return { label: 'Retadores', color: '#356ae6' };
  if (high_a && !high_p) return { label: 'Especializados', color: '#b45309' };
  return { label: 'Emergentes', color: '#7c3aed' };
}

// ─── ExecKPICard ─────────────────────────────────────────────────────────────

function ExecKPICard({ title, value, subtext, icon: Icon, color, trend }) {
  const isUp = trend >= 0;
  return (
    <div className="exec-kpi-card" style={{ '--kpi-accent': color }}>
      <div className="exec-kpi-top">
        <span className="exec-kpi-label">{title}</span>
        <span className="exec-kpi-icon" style={{ background: `${color}22` }}>
          <Icon size={18} color={color} />
        </span>
      </div>
      <div className="exec-kpi-value">{value}</div>
      {trend !== undefined && trend !== null && (
        <div className={`exec-kpi-trend ${isUp ? 'exec-trend-up' : 'exec-trend-down'}`}>
          {isUp ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
          <span>{isUp ? '+' : ''}{fmt(trend)}% vs. mes anterior</span>
        </div>
      )}
      {subtext && trend === undefined && <div className="exec-kpi-subtext">{subtext}</div>}
      {subtext && trend !== undefined && trend === null && <div className="exec-kpi-subtext">{subtext}</div>}
    </div>
  );
}

// ─── Quadrant scatter tooltip ────────────────────────────────────────────────

const QuadrantTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="recharts-default-tooltip">
      <p className="recharts-tooltip-label" style={{ fontWeight: 700 }}>{d.nombre_agente}</p>
      <p className="recharts-tooltip-item">Adopción: <span className="tooltip-value">{fmtCompact(d.adopcion)}</span></p>
      <p className="recharts-tooltip-item">Popularidad: <span className="tooltip-value">{fmtCompact(d.popularidad)}</span></p>
      <p className="recharts-tooltip-item" style={{ color: d._q?.color, fontWeight: 600 }}>
        {d._q?.label ?? '—'}
      </p>
    </div>
  );
};

// ─── Quadrant scatter chart ──────────────────────────────────────────────────

function QuadrantScatter({ data }) {
  const validData = (data || [])
    .map(item => ({
      ...item,
      adopcion: toNum(item.adopcion),
      popularidad: toNum(item.popularidad),
      total_observaciones: toNum(item.total_observaciones)
    }))
    .filter(item => item.adopcion > 0 || item.popularidad > 0);

  if (validData.length === 0) {
    return (
      <div className="panel chart-panel-lg">
        <h2>Mapa de Posicionamiento Competitivo</h2>
        <p className="chart-description">Sin datos disponibles para el período seleccionado.</p>
      </div>
    );
  }

  const midIdx = Math.floor(validData.length / 2);
  const medAdop = [...validData].sort((a, b) => a.adopcion - b.adopcion)[midIdx]?.adopcion || 0;
  const medPop = [...validData].sort((a, b) => a.popularidad - b.popularidad)[midIdx]?.popularidad || 0;

  const coloredData = validData.map(item => ({
    ...item,
    _q: quadrantMeta(item.adopcion, item.popularidad, medAdop, medPop)
  }));

  // Show labels for top agents by combined score
  const labelSet = new Set(
    [...coloredData]
      .sort((a, b) => b.adopcion + b.popularidad - (a.adopcion + a.popularidad))
      .slice(0, 8)
      .map(d => d.nombre_agente)
  );

  const CustomDot = (props) => {
    const { cx, cy, payload } = props;
    const q = payload._q;
    const r = Math.max(6, Math.min(18, 6 + toNum(payload.total_observaciones) / 60));
    const showLabel = labelSet.has(payload.nombre_agente);
    const name = payload.nombre_agente;
    const trimmed = name.length > 13 ? name.slice(0, 12) + '…' : name;
    return (
      <g>
        <circle cx={cx} cy={cy} r={r} fill={q.color} fillOpacity={0.7} stroke={q.color} strokeWidth={1.5} />
        {showLabel && (
          <text
            x={cx}
            y={cy - r - 5}
            textAnchor="middle"
            fill="var(--text-primary)"
            fontSize={10}
            fontWeight={700}
            style={{ pointerEvents: 'none' }}
          >
            {trimmed}
          </text>
        )}
      </g>
    );
  };

  const QUADRANTS = [
    { label: 'Líderes', color: '#16a36a', desc: 'Alta adopción y popularidad' },
    { label: 'Retadores', color: '#356ae6', desc: 'Alta popularidad, baja adopción' },
    { label: 'Especializados', color: '#b45309', desc: 'Alta adopción, menor visibilidad' },
    { label: 'Emergentes', color: '#7c3aed', desc: 'Por debajo de las medianas del mercado' },
  ];

  return (
    <div className="panel chart-panel-lg exec-quadrant-panel">
      <h2>Mapa de Posicionamiento Competitivo</h2>
      <p className="chart-description">
        Cada punto es un agente de IA. Eje X = adopción acumulada · Eje Y = popularidad. Las líneas marcan la mediana del mercado.
      </p>
      <div className="exec-quadrant-legend">
        {QUADRANTS.map(q => (
          <div key={q.label} className="exec-quadrant-legend-item">
            <span className="exec-quadrant-dot" style={{ background: q.color }} />
            <strong style={{ color: q.color, fontSize: 12 }}>{q.label}</strong>
            <span className="exec-quadrant-desc">{q.desc}</span>
          </div>
        ))}
      </div>
      <div className="chart-body-lg">
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 30, right: 30, left: 10, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
            <XAxis type="number" dataKey="adopcion" name="Adopción" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} tickFormatter={fmtCompact}>
              <Label value="Adopción →" offset={-12} position="insideBottom" fill="var(--text-muted)" fontSize={11} />
            </XAxis>
            <YAxis type="number" dataKey="popularidad" name="Popularidad" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} tickFormatter={fmtCompact}>
              <Label value="Popularidad →" angle={-90} position="insideLeft" fill="var(--text-muted)" fontSize={11} dy={50} />
            </YAxis>
            <ZAxis type="number" dataKey="total_observaciones" range={[40, 280]} />
            <RechartsTooltip content={<QuadrantTooltip />} />
            <ReferenceLine x={medAdop} stroke="var(--text-muted)" strokeDasharray="4 4" strokeWidth={1.5}
              label={{ value: 'Med. Adopción', position: 'insideTopRight', fill: 'var(--text-muted)', fontSize: 9 }} />
            <ReferenceLine y={medPop} stroke="var(--text-muted)" strokeDasharray="4 4" strokeWidth={1.5}
              label={{ value: 'Med. Popularidad', position: 'insideBottomLeft', fill: 'var(--text-muted)', fontSize: 9 }} />
            <Scatter name="Agentes" data={coloredData} shape={<CustomDot />} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ─── Top 10 Popularity bar chart ─────────────────────────────────────────────

const TOP_COLORS = [
  '#356ae6', '#5b8def', '#7c3aed', '#16a36a', '#b45309',
  '#0ea5e9', '#a78bfa', '#34d399', '#f59e0b', '#64748b'
];

function TopPopularityChart({ data }) {
  const chartData = [...(data || [])]
    .sort((a, b) => toNum(b.popularidad) - toNum(a.popularidad))
    .slice(0, 10)
    .reverse()
    .map((item, i) => ({ ...item, popularidad: toNum(item.popularidad), _color: TOP_COLORS[i % TOP_COLORS.length] }));

  if (chartData.length === 0) {
    return (
      <div className="panel chart-panel">
        <h2>Top 10 por Popularidad</h2>
        <p className="chart-description">Sin datos disponibles.</p>
      </div>
    );
  }

  return (
    <div className="panel chart-panel">
      <h2>Top 10 por Popularidad</h2>
      <p className="chart-description">
        Visibilidad relativa de cada agente en el ecosistema. Un score mayor indica mayor presencia y reconocimiento en las fuentes analizadas.
      </p>
      <div className="chart-body">
        <ResponsiveContainer>
          <BarChart data={chartData} layout="vertical" margin={{ top: 10, right: 40, left: 110, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal vertical={false} stroke="var(--border-primary)" />
            <XAxis type="number" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} tickFormatter={fmtCompact} />
            <YAxis type="category" dataKey="nombre_agente" interval={0} tick={<CategoryAxisTick maxLength={16} />} width={105} />
            <RechartsTooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload;
                return (
                  <div className="recharts-default-tooltip">
                    <p className="recharts-tooltip-label" style={{ fontWeight: 700 }}>{d.nombre_agente}</p>
                    <p className="recharts-tooltip-item">Popularidad: <span className="tooltip-value">{fmtCompact(d.popularidad)}</span></p>
                    <p className="recharts-tooltip-item">Categoría: <span className="tooltip-value">{d.categoria_agente || '—'}</span></p>
                  </div>
                );
              }}
            />
            <Bar dataKey="popularidad" name="Popularidad" radius={[0, 4, 4, 0]}>
              {chartData.map((entry, index) => (
                <Cell key={index} fill={entry._color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function EjecutivoDashboard({ data }) {
  const ranking = data?.ranking || [];
  const tendencia = data?.tendencia || [];

  const { sorted, leader, runner, leaderGap, momGrowth, emergent } = useMemo(
    () => deriveMetrics(ranking, tendencia),
    [ranking, tendencia]
  );

  const narrative = useMemo(
    () => buildNarrative({ leader, runner, leaderGap, momGrowth, emergent, sorted }),
    [leader, runner, leaderGap, momGrowth, emergent, sorted]
  );

  const totalMenciones = ranking.reduce((s, item) => s + toNum(item.total_menciones), 0);

  return (
    <div className="exec-dashboard">
      {/* Narrative banner */}
      <div className="exec-narrative">
        <div className="exec-narrative-icon"><BarChart2 size={20} color="var(--primary)" /></div>
        <p>{narrative}</p>
      </div>

      {/* KPI row */}
      <div className="exec-kpi-row">
        <ExecKPICard
          title="Líder de Mercado"
          value={leader?.nombre_agente ?? '—'}
          subtext={leader ? `Score: ${fmtCompact(leader.adopcion)}` : undefined}
          icon={Award}
          color="var(--primary)"
        />
        <ExecKPICard
          title="Brecha vs. #2"
          value={leaderGap !== null ? `${fmt(leaderGap)}%` : '—'}
          subtext={runner ? `vs. ${runner.nombre_agente}` : undefined}
          icon={Target}
          color={leaderGap !== null && leaderGap >= 50 ? 'var(--success)' : 'var(--warning)'}
        />
        <ExecKPICard
          title="Crecimiento MoM"
          value={momGrowth !== null ? `${momGrowth >= 0 ? '+' : ''}${fmt(momGrowth)}%` : '—'}
          icon={TrendingUp}
          color={momGrowth !== null && momGrowth >= 0 ? 'var(--success)' : 'var(--danger)'}
          trend={momGrowth}
        />
        <ExecKPICard
          title="Mayor Intensidad"
          value={emergent?.nombre_agente ?? '—'}
          subtext="Adopción / observación más alta"
          icon={Zap}
          color="var(--accent)"
        />
        <ExecKPICard
          title="Menciones Totales"
          value={fmtCompact(totalMenciones)}
          subtext="Impacto global en todas las fuentes"
          icon={Star}
          color="var(--secondary)"
        />
      </div>

      {/* Charts */}
      <div className="exec-charts-grid">
        <QuadrantScatter data={ranking} />
        <TopPopularityChart data={ranking} />
      </div>
    </div>
  );
}
