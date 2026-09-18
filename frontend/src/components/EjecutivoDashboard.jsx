import React, { useMemo } from 'react';
import {
  XAxis, YAxis, CartesianGrid,
  Tooltip as RechartsTooltip, ResponsiveContainer,
  BarChart, Bar, Cell
} from 'recharts';
import { TrendingUp, TrendingDown, Zap, Award, Target, BarChart2, Star } from 'lucide-react';
import CompetitivePositioning from './CompetitivePositioning';
import { CategoryAxisTick, CHART_PALETTE } from './charts/Charts';

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

// ─── Top 10 Popularity bar chart ─────────────────────────────────────────────

function TopPopularityChart({ data }) {
  const chartData = [...(data || [])]
    .sort((a, b) => toNum(b.popularidad) - toNum(a.popularidad))
    .slice(0, 10)
    .reverse()
    .map((item, i) => ({ ...item, popularidad: toNum(item.popularidad), _color: CHART_PALETTE[i % CHART_PALETTE.length] }));

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
        Top 10 del total de agentes analizados. Popularidad: visibilidad relativa acumulada (menciones e interacciones normalizadas por fuente); no es un porcentaje ni un conteo directo de seguidores.
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
  const ranking = useMemo(() => data?.ranking || [], [data?.ranking]);
  const tendencia = useMemo(() => data?.tendencia || [], [data?.tendencia]);

  const { sorted, leader, runner, leaderGap, momGrowth, emergent } = useMemo(
    () => deriveMetrics(ranking, tendencia),
    [ranking, tendencia]
  );

  const narrative = useMemo(
    () => buildNarrative({ leader, runner, leaderGap, momGrowth, emergent, sorted }),
    [leader, runner, leaderGap, momGrowth, emergent, sorted]
  );

  // Suma sobre TODOS los agentes del agregado (el backend entrega el ranking completo).
  const totalMenciones = useMemo(
    () => ranking.reduce((s, item) => s + toNum(item.total_menciones), 0),
    [ranking]
  );

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
          subtext={leader ? `Score de adopción: ${fmtCompact(leader.adopcion)}` : undefined}
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
          subtext="Mayor score de adopción por observación"
          icon={Zap}
          color="var(--accent)"
        />
        <ExecKPICard
          title="Menciones Totales"
          value={fmtCompact(totalMenciones)}
          subtext="Suma sobre todos los agentes y fuentes analizadas"
          icon={Star}
          color="var(--secondary)"
        />
      </div>

      {/* Charts */}
      <div className="exec-charts-grid">
        <CompetitivePositioning data={ranking} />
        <TopPopularityChart data={ranking} />
      </div>
    </div>
  );
}
