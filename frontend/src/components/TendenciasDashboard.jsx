import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  CalendarClock,
  Database,
  Info,
  TrendingUp,
  Users
} from 'lucide-react';
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';
import { KPICard } from './KPI';
import { fetchCommunityTrend } from '../services/api';

const MONTH_ABBR = {
  1: 'ene.', 2: 'feb.', 3: 'mar.', 4: 'abr.', 5: 'may.', 6: 'jun.',
  7: 'jul.', 8: 'ago.', 9: 'sep.', 10: 'oct.', 11: 'nov.', 12: 'dic.'
};

const SOURCE_LABELS = {
  catalogo: 'AIDev / catálogo',
  github: 'GitHub',
  reddit: 'Reddit',
  devto: 'Dev.to',
  hackernews: 'Hacker News',
  google_trends: 'Google Trends',
  fuente_propia: 'Encuesta UPSE',
  stackoverflow: 'Stack Overflow',
  gnews: 'Google News',
  arxiv: 'arXiv'
};

const METRICS = {
  adopcion: { label: 'Adopción', field: 'adopcion' },
  observaciones: { label: 'Observaciones', field: 'total_observaciones' },
  interacciones: { label: 'Interacciones', field: 'total_interacciones' }
};

const toNumber = value => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const formatNumber = (value, maximumFractionDigits = 1) => (
  toNumber(value).toLocaleString('es-EC', { maximumFractionDigits })
);

const formatCompact = value => new Intl.NumberFormat('es-EC', {
  notation: 'compact',
  maximumFractionDigits: 1
}).format(toNumber(value));

const formatHeatValue = value => toNumber(value) < 1 ? formatNumber(value, 2) : formatCompact(value);

const formatMonth = item => `${MONTH_ABBR[toNumber(item.mes)] || item.nombre_mes} ${item.anio}`;

function buildTrendData(data, scaleMode) {
  const sorted = [...(data || [])].sort((a, b) => toNumber(a.anio) - toNumber(b.anio) || toNumber(a.mes) - toNumber(b.mes));
  return sorted.map((item, index) => {
    const value = toNumber(item.suma_adopcion);
    const previous = index > 0 ? toNumber(sorted[index - 1].suma_adopcion) : 0;
    const window = sorted.slice(Math.max(0, index - 2), index + 1);
    const movingAverage = window.reduce((sum, row) => sum + toNumber(row.suma_adopcion), 0) / window.length;
    return {
      ...item,
      name: formatMonth(item),
      valor: value,
      promedio: movingAverage,
      valorGrafico: scaleMode === 'log' ? Math.max(value, 0.1) : value,
      promedioGrafico: scaleMode === 'log' ? Math.max(movingAverage, 0.1) : movingAverage,
      variacion: previous > 0 ? ((value - previous) / previous) * 100 : null
    };
  });
}

function TrendTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const item = payload[0].payload;
  return (
    <div className="recharts-default-tooltip trend-tooltip">
      <p className="recharts-tooltip-label">{item.name}</p>
      <p>Índice de adopción: <strong>{formatNumber(item.valor, 2)}</strong></p>
      <p>Promedio móvil (3 meses): <strong>{formatNumber(item.promedio, 2)}</strong></p>
      <p>Variación mensual: <strong>{item.variacion == null ? 'Sin base comparable' : `${item.variacion >= 0 ? '+' : ''}${formatNumber(item.variacion)} %`}</strong></p>
      <p>Fuente predominante: <strong>{SOURCE_LABELS[item.fuente_predominante] || item.fuente_predominante || 'No disponible'}</strong></p>
    </div>
  );
}

function AdoptionTrendChart({ data, communityOnly, onToggleCommunity, loadingCommunity }) {
  const [scaleMode, setScaleMode] = useState('linear');
  const chartData = useMemo(() => buildTrendData(data, scaleMode), [data, scaleMode]);
  const peak = useMemo(() => chartData.reduce((maximum, item) => item.valor > (maximum?.valor || 0) ? item : maximum, null), [chartData]);
  const peakSource = peak ? (SOURCE_LABELS[peak.fuente_predominante] || peak.fuente_predominante || 'las fuentes activas') : '';

  if (chartData.length === 0) {
    return <section className="panel trend-primary-panel"><h2>Índice mensual de adopción</h2><div className="chart-empty-state">No hay tendencia para los filtros seleccionados.</div></section>;
  }

  return (
    <section className="panel trend-primary-panel">
      <div className="trend-panel-header">
        <div>
          <div className="trend-title-line">
            <h2>Índice mensual de adopción</h2>
            <button
              className="metric-help"
              type="button"
              aria-label="Cómo se calcula el índice de adopción"
              title="Suma mensual del índice de adopción normalizado por registro. En las fuentes que lo aportan, cada registro se calcula sobre una escala de 0 a 100."
            >
              <Info size={15} />
            </button>
          </div>
          <p>Índice agregado y promedio móvil de tres meses.</p>
        </div>
        <div className="trend-chart-controls" aria-label="Controles del gráfico">
          <div className="segmented-control">
            <button className={scaleMode === 'linear' ? 'active' : ''} onClick={() => setScaleMode('linear')}>Lineal</button>
            <button className={scaleMode === 'log' ? 'active' : ''} onClick={() => setScaleMode('log')}>Logarítmica</button>
          </div>
          <button className={`community-toggle ${communityOnly ? 'active' : ''}`} onClick={onToggleCommunity}>
            {loadingCommunity ? 'Calculando…' : 'Solo comunidad'}
          </button>
        </div>
      </div>

      {peak && peak.valor > 0 && (
        <div className="peak-annotation">
          <TrendingUp size={15} />
          <span>
            <strong>{peak.name}:</strong>{' '}
            {peak.fuente_predominante === 'catalogo'
              ? 'incremento asociado a la incorporación masiva del AIDev Dataset.'
              : `máximo del periodo, con predominio de ${peakSource}.`}
          </span>
        </div>
      )}

      <div className="trend-chart-body">
        <ResponsiveContainer>
          <ComposedChart data={chartData} margin={{ top: 18, right: 18, left: 0, bottom: 4 }}>
            <defs>
              <linearGradient id="trendAdoptionFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.28} />
                <stop offset="95%" stopColor="var(--primary)" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--grid-color)" />
            <XAxis dataKey="name" interval="preserveStartEnd" minTickGap={48} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
            <YAxis
              scale={scaleMode === 'log' ? 'log' : 'auto'}
              domain={scaleMode === 'log' ? [0.1, 'auto'] : [0, 'auto']}
              tickFormatter={formatCompact}
              tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
              width={52}
            />
            <Tooltip content={<TrendTooltip />} />
            <Legend verticalAlign="top" height={32} />
            <Area type="monotone" dataKey="valorGrafico" name="Adopción" stroke="var(--primary)" strokeWidth={2.4} fill="url(#trendAdoptionFill)" />
            <Line type="monotone" dataKey="promedioGrafico" name="Promedio móvil 3M" stroke="var(--accent)" strokeWidth={2} dot={false} />
            {peak && <ReferenceLine x={peak.name} stroke="var(--accent)" strokeDasharray="4 4" />}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function SourceContributionChart({ data, communityOnly }) {
  const chartData = useMemo(() => {
    const filtered = (data || []).filter(item => !communityOnly || item.tipo_fuente !== 'catalogo');
    const total = filtered.reduce((sum, item) => sum + toNumber(item.total_observaciones), 0);
    return filtered
      .map(item => ({
        ...item,
        fuente: SOURCE_LABELS[item.nombre_fuente] || item.nombre_fuente,
        participacion: total > 0 ? (toNumber(item.total_observaciones) / total) * 100 : 0
      }))
      .sort((a, b) => b.participacion - a.participacion)
      .slice(0, 7)
      .reverse();
  }, [communityOnly, data]);

  if (chartData.length === 0) {
    return <section className="panel trend-source-panel"><h2>Contribución por fuente</h2><div className="chart-empty-state">No hay fuentes para el periodo seleccionado.</div></section>;
  }

  return (
    <section className="panel trend-source-panel">
      <div className="trend-panel-header compact">
        <div><h2>Contribución por fuente</h2><p>Participación en el periodo seleccionado.</p></div>
      </div>
      <div className="source-chart-body">
        <ResponsiveContainer>
          <BarChart data={chartData} layout="vertical" margin={{ top: 8, right: 20, left: 18, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--grid-color)" />
            <XAxis type="number" domain={[0, 'auto']} tickFormatter={value => `${formatNumber(value, 0)}%`} tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} />
            <YAxis type="category" dataKey="fuente" interval={0} tickMargin={8} width={98} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
            <Tooltip formatter={value => [`${formatNumber(value)} %`, 'Participación']} />
            <Bar dataKey="participacion" fill="var(--primary)" radius={[0, 5, 5, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function TrendHeatmap({ data }) {
  const [metric, setMetric] = useState('adopcion');
  const metricConfig = METRICS[metric];

  const { months, agents, valueMap, globalMax, rowMax } = useMemo(() => {
    const monthMap = new Map();
    (data || []).forEach(item => {
      const key = `${item.anio}-${String(item.mes).padStart(2, '0')}`;
      monthMap.set(key, { key, anio: toNumber(item.anio), mes: toNumber(item.mes), label: formatMonth(item) });
    });
    const monthList = [...monthMap.values()]
      .sort((a, b) => a.anio - b.anio || a.mes - b.mes)
      .slice(-18);
    const allowedMonths = new Set(monthList.map(item => item.key));
    const map = new Map();
    const totals = new Map();
    const maxima = new Map();
    let maximum = 0;

    (data || []).forEach(item => {
      const monthKey = `${item.anio}-${String(item.mes).padStart(2, '0')}`;
      if (!allowedMonths.has(monthKey)) return;
      const value = toNumber(item[metricConfig.field]);
      const key = `${item.nombre_agente}__${monthKey}`;
      map.set(key, value);
      totals.set(item.nombre_agente, (totals.get(item.nombre_agente) || 0) + value);
      maxima.set(item.nombre_agente, Math.max(maxima.get(item.nombre_agente) || 0, value));
      maximum = Math.max(maximum, value);
    });

    return {
      months: monthList,
      agents: [...totals.entries()].sort((a, b) => b[1] - a[1]).map(([name]) => name),
      valueMap: map,
      globalMax: Math.max(maximum, 1),
      rowMax: maxima
    };
  }, [data, metricConfig.field]);

  const cellColor = value => value <= 0
    ? 'var(--heatmap-empty)'
    : `rgba(53, 106, 230, ${(0.12 + (value / globalMax) * 0.78).toFixed(2)})`;

  if (months.length === 0) {
    return <section className="panel trend-heatmap-panel"><h2>Mapa de calor: agentes × meses</h2><div className="chart-empty-state">No hay datos mensuales por agente.</div></section>;
  }

  return (
    <section className="panel trend-heatmap-panel">
      <div className="trend-panel-header heatmap-panel-header">
        <div><h2>Mapa de calor: agentes × meses</h2><p>Últimos 18 meses, agentes ordenados por acumulado.</p></div>
        <div className="heatmap-toolbar">
          <label htmlFor="heatmap-metric">Métrica</label>
          <select id="heatmap-metric" value={metric} onChange={event => setMetric(event.target.value)}>
            {Object.entries(METRICS).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}
          </select>
          <div className="heatmap-legend"><span>Baja</span><i /><span>Alta</span></div>
        </div>
      </div>

      <div className="enhanced-heatmap-wrapper">
        <div className="enhanced-heatmap" style={{ gridTemplateColumns: `170px repeat(${months.length}, minmax(62px, 1fr))` }}>
          <div className="enhanced-heatmap-corner">Agente</div>
          {months.map(month => <div key={month.key} className="enhanced-heatmap-header">{month.label}</div>)}
          {agents.map(agent => (
            <React.Fragment key={agent}>
              <div className="enhanced-heatmap-agent">{agent}</div>
              {months.map(month => {
                const value = valueMap.get(`${agent}__${month.key}`) || 0;
                const isMax = value > 0 && value === rowMax.get(agent);
                return (
                  <div
                    key={`${agent}-${month.key}`}
                    className={`enhanced-heatmap-cell ${isMax ? 'is-row-max' : ''}`}
                    style={{ backgroundColor: cellColor(value) }}
                    title={`${agent} · ${month.label}: ${formatNumber(value, 2)} ${metricConfig.label.toLowerCase()}`}
                  >
                    {value > 0 ? formatHeatValue(value) : ''}
                  </div>
                );
              })}
            </React.Fragment>
          ))}
        </div>
      </div>
    </section>
  );
}

function InsightPanels({ tendencia, fuentes, ranking }) {
  const variations = useMemo(() => {
    const sorted = [...(tendencia || [])].sort((a, b) => toNumber(a.anio) - toNumber(b.anio) || toNumber(a.mes) - toNumber(b.mes));
    return sorted.slice(1).map((item, index) => {
      const previous = toNumber(sorted[index].total_observaciones);
      const current = toNumber(item.total_observaciones);
      return { label: formatMonth(item), value: previous > 0 ? ((current - previous) / previous) * 100 : 0 };
    }).sort((a, b) => Math.abs(b.value) - Math.abs(a.value)).slice(0, 3);
  }, [tendencia]);

  const peak = useMemo(() => (tendencia || []).reduce((maximum, item) => toNumber(item.total_observaciones) > toNumber(maximum?.total_observaciones) ? item : maximum, null), [tendencia]);
  const topSource = fuentes?.[0];
  const topAgent = ranking?.[0];

  return (
    <div className="trend-insights-grid">
      <section className="panel insight-panel">
        <h2>Principales variaciones</h2>
        <div className="variation-list">
          {variations.map(item => (
            <div key={item.label}>
              <span>{item.label}</span>
              <strong className={item.value >= 0 ? 'positive' : 'negative'}>{item.value >= 0 ? '+' : ''}{formatNumber(item.value)} %</strong>
            </div>
          ))}
        </div>
      </section>
      <section className="panel insight-panel">
        <h2>Hallazgos automáticos</h2>
        <ul className="findings-list">
          {peak && <li>El mayor volumen se concentra en <strong>{formatMonth(peak)}</strong> con {formatNumber(peak.total_observaciones, 0)} observaciones.</li>}
          {topSource && <li><strong>{SOURCE_LABELS[topSource.nombre_fuente] || topSource.nombre_fuente}</strong> aporta {formatNumber(topSource.porcentaje_participacion)} % del periodo.</li>}
          {topAgent && <li><strong>{topAgent.nombre_agente}</strong> lidera el índice acumulado de adopción.</li>}
        </ul>
      </section>
    </div>
  );
}

export default function TendenciasDashboard({ data, filters }) {
  const [communityOnly, setCommunityOnly] = useState(false);
  const [communityTrend, setCommunityTrend] = useState([]);
  const [loadingCommunity, setLoadingCommunity] = useState(false);

  useEffect(() => {
    if (!communityOnly) return undefined;
    let mounted = true;
    setLoadingCommunity(true);
    fetchCommunityTrend(filters)
      .then(result => { if (mounted) setCommunityTrend(result); })
      .catch(() => { if (mounted) setCommunityTrend([]); })
      .finally(() => { if (mounted) setLoadingCommunity(false); });
    return () => { mounted = false; };
  }, [communityOnly, filters]);

  const tendency = communityOnly ? communityTrend : (data.tendencia || []);
  const totalObservations = (data.distribucion || []).reduce((sum, item) => sum + toNumber(item.total_observaciones), 0);
  const adoptionScore = (data.ranking || []).reduce((sum, item) => sum + toNumber(item.adopcion), 0);
  const sortedGrowth = [...(data.crecimiento || [])].sort((a, b) => toNumber(a.anio) - toNumber(b.anio) || toNumber(a.mes) - toNumber(b.mes));
  const currentDate = new Date();
  const lastGrowthIndex = sortedGrowth.length > 1 && toNumber(sortedGrowth.at(-1)?.mes) === currentDate.getMonth() + 1 && currentDate.getDate() < 25 ? sortedGrowth.length - 2 : sortedGrowth.length - 1;
  const latestGrowth = sortedGrowth[lastGrowthIndex];
  const growthValue = toNumber(latestGrowth?.variacion_porcentual);
  const executionDate = data.qualitySummary?.execution_date;
  const updateDate = executionDate ? new Date(executionDate.endsWith('Z') ? executionDate : `${executionDate}Z`) : currentDate;
  const updateLabel = updateDate.toLocaleDateString('es-EC', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'America/Guayaquil' }).replace('.', '');

  return (
    <div className="trends-dashboard">
      <div className="trend-kpi-grid">
        <KPICard title="Observaciones totales" value={formatNumber(totalObservations, 0)} subtext="Registros del periodo" icon={Database} color="var(--primary)" sparklineData={data.tendencia} sparklineDataKey="total_observaciones" />
        <KPICard title="Score de adopción" value={formatNumber(adoptionScore, 2)} subtext="Índice acumulado" icon={Activity} color="var(--primary)" sparklineData={data.tendencia} sparklineDataKey="suma_adopcion" />
        <KPICard title="Agentes analizados" value={(data.ranking || []).length} subtext="Con actividad identificada" icon={Users} color="var(--primary)" />
        <KPICard title="Crecimiento mensual" value={`${growthValue >= 0 ? '+' : ''}${formatNumber(growthValue)} %`} subtext={latestGrowth ? `${formatMonth(latestGrowth)} · último mes completo` : 'Sin comparación'} icon={TrendingUp} color={growthValue >= 0 ? 'var(--success)' : 'var(--danger)'} />
        <KPICard title="Última actualización" value={updateLabel} subtext="Carga validada del DW" icon={CalendarClock} color="var(--primary)" />
      </div>

      <div className="trend-main-grid">
        <AdoptionTrendChart data={tendency} communityOnly={communityOnly} onToggleCommunity={() => setCommunityOnly(previous => !previous)} loadingCommunity={loadingCommunity} />
        <SourceContributionChart data={data.participacion || []} communityOnly={communityOnly} />
      </div>

      <TrendHeatmap data={data.tendenciaAgentes || []} />
      <InsightPanels tendencia={tendency} fuentes={data.participacion || []} ranking={data.ranking || []} />
    </div>
  );
}
