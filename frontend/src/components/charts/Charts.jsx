import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer,
  PieChart, Pie, Cell, AreaChart, Area, ScatterChart, Scatter, ZAxis, ReferenceLine, Legend, Label
} from 'recharts';

const CHART_COLORS = [
  "var(--primary)", "var(--secondary)", "var(--accent)", 
  "var(--warning)", "var(--info)", "var(--neutral)"
];

const QUALITY_SOURCE_LABELS = {
  arxiv: 'arXiv', catalogo: 'Catálogo', devto: 'Dev.to', fuente_propia: 'Fuente propia',
  github: 'GitHub', gnews: 'Google News', google_trends: 'Google Trends',
  hackernews: 'Hacker News', reddit: 'Reddit', stackoverflow: 'Stack Overflow'
};

const RANKING_DESCRIPTIONS = {
  adopcion: 'Ordena los agentes por su score acumulado de adopción. Una barra más larga indica mayor presencia y uso observado en las fuentes analizadas.',
  popularidad: 'Compara la visibilidad relativa de los agentes. Una barra más larga representa mayor señal agregada de popularidad.',
  comunidad: 'Mide la señal comunitaria acumulada de cada agente. Una barra más larga indica mayor presencia e interacción en fuentes de comunidad.',
  innovacion: 'Resume señales asociadas con novedad y avance tecnológico. Una barra más larga indica mayor score de innovación dentro del periodo.',
  actividad: 'Compara la intensidad total de actividad registrada por agente. Una barra más larga representa mayor volumen de señales observadas.'
};

const ChartDescription = ({ children }) => <p className="chart-description">{children}</p>;

const toNumber = value => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const EmptyChart = ({ title, description, large = false, message = 'No hay datos para los filtros seleccionados.' }) => (
  <div className={`panel ${large ? 'chart-panel-lg' : 'chart-panel'}`}>
    <h2>{title}</h2>
    {description && <ChartDescription>{description}</ChartDescription>}
    <div className="chart-empty-state"><p>{message}</p></div>
  </div>
);

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const displayLabel = label ?? payload[0]?.payload?.categoria_agente ?? payload[0]?.payload?.name;
    return (
      <div className="recharts-default-tooltip">
        {displayLabel && <p className="recharts-tooltip-label">{displayLabel}</p>}
        {payload.map((entry, index) => (
          <p key={index} className="recharts-tooltip-item" style={{ color: entry.color }}>
            {entry.name}: <span className="tooltip-value">{typeof entry.value === 'number' ? entry.value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : entry.value}</span>
          </p>
        ))}
      </div>
    );
  }
  return null;
};

const CategoryAxisTick = ({ x, y, payload, maxLength = 20, fontWeight = 500 }) => {
  const label = String(payload?.value ?? '');
  const visibleLabel = label.length > maxLength
    ? `${label.slice(0, maxLength - 1).trimEnd()}…`
    : label;

  return (
    <g transform={`translate(${x},${y})`}>
      <title>{label}</title>
      <text x={-8} y={0} dy="0.32em" textAnchor="end" fill="var(--text-secondary)" fontSize={11} fontWeight={fontWeight}>
        {visibleLabel}
      </text>
    </g>
  );
};

export const RankingBarChart = ({ data, metric, title, color }) => {
  const description = RANKING_DESCRIPTIONS[metric] || 'Compara el valor acumulado de cada agente para la métrica seleccionada.';
  const chartData = (data || [])
    .map(item => ({ ...item, [metric]: toNumber(item[metric]) }))
    .filter(item => item[metric] > 0);

  if (chartData.length === 0) return <EmptyChart title={title} description={description} />;

  return (
    <div className="panel chart-panel">
      <h2>{title}</h2>
      <ChartDescription>{description}</ChartDescription>
      <div className="chart-body">
        <ResponsiveContainer>
          <BarChart data={chartData} layout="vertical" margin={{ top: 10, right: 30, left: 100, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="var(--border-primary)" />
            <XAxis type="number" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
            <YAxis type="category" dataKey="nombre_agente" interval={0} tick={<CategoryAxisTick maxLength={18} fontWeight={600} />} width={110} />
            <RechartsTooltip content={<CustomTooltip />} />
            <Bar dataKey={metric} name="Puntuación" fill={color || "var(--primary)"} radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export const TendenciaLineChart = ({ data, metricKey, metricName, color }) => {
  const title = `Evolución Temporal: ${metricName}`;
  const description = `Muestra cómo cambia ${metricName.toLowerCase()} mes a mes. Los picos señalan periodos de mayor intensidad y el área facilita reconocer la tendencia general.`;
  const gradientId = `metric-gradient-${metricKey.replace(/[^a-z0-9_-]/gi, '-')}`;
  const chartData = (data || []).map(item => ({
    name: `${item.nombre_mes} ${item.anio}`,
    valor: toNumber(item[metricKey])
  }));

  if (!chartData.some(item => item.valor > 0)) return <EmptyChart title={title} description={description} />;

  return (
    <div className="panel chart-panel">
      <h2>{title}</h2>
      <ChartDescription>{description}</ChartDescription>
      <div className="chart-body">
        <ResponsiveContainer>
          <AreaChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 50 }}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color || "var(--primary)"} stopOpacity={0.8}/>
                <stop offset="95%" stopColor={color || "var(--primary)"} stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-primary)" />
            <XAxis dataKey="name" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} angle={-45} textAnchor="end" />
            <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
            <RechartsTooltip content={<CustomTooltip />} />
            <Area type="monotone" dataKey="valor" name={metricName} stroke={color || "var(--primary)"} fillOpacity={1} fill={`url(#${gradientId})`} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export const ComparadorAgentesChart = ({ data }) => {
  const title = 'Comparativa de Líderes (Adopción vs Popularidad)';
  const description = 'Contrasta adopción en azul con popularidad en violeta para los líderes. Cada métrica usa su propio eje, por lo que debe compararse la posición relativa de cada agente.';
  const chartData = (data || []).map(item => ({
    ...item,
    adopcion: toNumber(item.adopcion),
    popularidad: toNumber(item.popularidad)
  }));

  if (!chartData.some(item => item.adopcion > 0 || item.popularidad > 0)) return <EmptyChart title={title} description={description} />;

  return (
    <div className="panel chart-panel">
      <h2>{title}</h2>
      <ChartDescription>{description}</ChartDescription>
      <div className="chart-body">
        <ResponsiveContainer>
          <BarChart data={chartData} margin={{ top: 20, right: 10, left: 10, bottom: 50 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-primary)" />
            <XAxis dataKey="nombre_agente" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} angle={-45} textAnchor="end" />
            <YAxis yAxisId="left" orientation="left" tick={{ fill: 'var(--primary)', fontSize: 12 }} />
            <YAxis yAxisId="right" orientation="right" tick={{ fill: 'var(--secondary)', fontSize: 12 }} />
            <RechartsTooltip content={<CustomTooltip />} />
            <Legend verticalAlign="top" height={36}/>
            <Bar yAxisId="left" dataKey="adopcion" name="Adopción" fill="var(--primary)" radius={[4, 4, 0, 0]} />
            <Bar yAxisId="right" dataKey="popularidad" name="Popularidad" fill="var(--secondary)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export const FuenteBarChart = ({ data }) => {
  const title = 'Participación por Fuente';
  const description = 'Distribuye las observaciones según su fuente de origen. Una barra más larga indica que esa fuente aporta mayor volumen al análisis.';
  const chartData = (data || [])
    .map(item => ({ ...item, total_observaciones: toNumber(item.total_observaciones) }))
    .filter(item => item.total_observaciones > 0)
    .sort((a, b) => b.total_observaciones - a.total_observaciones);

  if (chartData.length === 0) return <EmptyChart title={title} description={description} />;

  return (
    <div className="panel chart-panel">
      <h2>{title}</h2>
      <ChartDescription>{description}</ChartDescription>
      <div className="chart-body">
        <ResponsiveContainer>
          <BarChart data={chartData} layout="vertical" margin={{ top: 20, right: 30, left: 120, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="var(--border-primary)" />
            <XAxis type="number" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
            <YAxis type="category" dataKey="nombre_fuente" interval={0} tick={<CategoryAxisTick maxLength={18} />} width={110} />
            <RechartsTooltip content={<CustomTooltip />} />
            <Bar dataKey="total_observaciones" name="Observaciones" fill="var(--secondary)" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

const ScatterTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="recharts-default-tooltip">
        <p className="recharts-tooltip-label">{data.nombre_agente}</p>
        <p className="recharts-tooltip-item">Adopción: <span className="tooltip-value">{data.adopcion}</span></p>
        <p className="recharts-tooltip-item">Popularidad: <span className="tooltip-value">{data.popularidad}</span></p>
        <p className="recharts-tooltip-item">Observaciones: <span className="tooltip-value">{data.total_observaciones}</span></p>
      </div>
    );
  }
  return null;
};

export const PosicionamientoScatterChart = ({ data }) => {
  const title = 'Posicionamiento: Adopción vs Popularidad';
  const description = 'Cada punto representa un agente: más a la derecha significa mayor adopción, más arriba mayor popularidad y un punto más grande mayor volumen de observaciones. Las líneas dividen los cuadrantes por mediana.';
  const validData = (data || []).map(item => ({
    ...item,
    adopcion: toNumber(item.adopcion),
    popularidad: toNumber(item.popularidad),
    total_observaciones: toNumber(item.total_observaciones)
  })).filter(item => item.adopcion > 0 || item.popularidad > 0);
  if (validData.length === 0) return <EmptyChart title={title} description={description} large />;
  
  const sortedAdop = [...validData].sort((a,b) => a.adopcion - b.adopcion);
  const medAdop = sortedAdop[Math.floor(sortedAdop.length/2)]?.adopcion || 0;
  
  const sortedPop = [...validData].sort((a,b) => a.popularidad - b.popularidad);
  const medPop = sortedPop[Math.floor(sortedPop.length/2)]?.popularidad || 0;

  return (
    <div className="panel chart-panel-lg">
      <h2>{title}</h2>
      <ChartDescription>{description}</ChartDescription>
      <div className="chart-body-lg">
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
            <XAxis type="number" dataKey="adopcion" name="Adopción" tick={{ fill: 'var(--text-secondary)' }} />
            <YAxis type="number" dataKey="popularidad" name="Popularidad" tick={{ fill: 'var(--text-secondary)' }} />
            <ZAxis type="number" dataKey="total_observaciones" range={[50, 400]} name="Observaciones" />
            <RechartsTooltip content={<ScatterTooltip />} />
            <ReferenceLine x={medAdop} stroke="var(--text-muted)" strokeDasharray="3 3" label={{ position: 'insideTopLeft', value: 'Mediana Adop.', fill: 'var(--text-muted)', fontSize: 10 }} />
            <ReferenceLine y={medPop} stroke="var(--text-muted)" strokeDasharray="3 3" label={{ position: 'insideBottomRight', value: 'Mediana Pop.', fill: 'var(--text-muted)', fontSize: 10 }} />
            <Scatter name="Agentes" data={validData} fill="var(--primary)" fillOpacity={0.6} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export const CategoriaPieChart = ({ data }) => {
  const title = 'Distribución por Categoría';
  const description = 'Muestra qué proporción del score de adopción corresponde a cada categoría de agente. Un segmento mayor indica más peso dentro del total analizado.';
  const normalized = (data || []).map(item => ({
    ...item,
    adopcion: toNumber(item.adopcion),
    total_observaciones: toNumber(item.total_observaciones)
  }));
  const metric = normalized.some(item => item.adopcion > 0) ? 'adopcion' : 'total_observaciones';
  const sorted = normalized
    .map(item => ({ ...item, valor: item[metric] }))
    .filter(item => item.valor > 0)
    .sort((a, b) => b.valor - a.valor);
  const topCategories = sorted.slice(0, 6);
  const otherValue = sorted.slice(6).reduce((sum, item) => sum + item.valor, 0);
  const chartData = otherValue > 0
    ? [...topCategories, { categoria_agente: 'Otros', valor: otherValue }]
    : topCategories;

  if (chartData.length === 0) return <EmptyChart title={title} description={description} />;

  return (
    <div className="panel chart-panel category-chart-panel">
      <h2>{title}</h2>
      <ChartDescription>{description}</ChartDescription>
      <div className="category-chart-content">
        <div className="category-donut">
          <ResponsiveContainer>
            <PieChart>
              <Pie data={chartData} cx="50%" cy="50%" innerRadius={62} outerRadius={98} paddingAngle={3} dataKey="valor" nameKey="categoria_agente" stroke="none">
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                ))}
              </Pie>
              <RechartsTooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="category-legend" aria-label="Categorías representadas">
          {chartData.map((entry, index) => (
            <div className="category-legend-item" key={entry.categoria_agente} title={entry.categoria_agente}>
              <span style={{ backgroundColor: CHART_COLORS[index % CHART_COLORS.length] }} />
              <span>{entry.categoria_agente}</span>
              <strong>{((entry.valor / chartData.reduce((sum, item) => sum + item.valor, 0)) * 100).toLocaleString('es-EC', { maximumFractionDigits: 1 })}%</strong>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export const TecnologiaBarChart = ({ data }) => {
  const title = 'Adopción por Dominio Tecnológico';
  const description = 'Agrupa la adopción por dominio tecnológico. Una barra más larga señala los ámbitos donde se concentra una mayor señal de uso.';
  const chartData = (data || [])
    .map(item => ({ ...item, adopcion: toNumber(item.adopcion) }))
    .filter(item => item.adopcion > 0)
    .sort((a, b) => b.adopcion - a.adopcion);

  if (chartData.length === 0) return <EmptyChart title={title} description={description} />;

  return (
    <div className="panel chart-panel">
      <h2>{title}</h2>
      <ChartDescription>{description}</ChartDescription>
      <div className="chart-body">
        <ResponsiveContainer>
          <BarChart data={chartData} layout="vertical" margin={{ top: 20, right: 30, left: 155, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="var(--border-primary)" />
            <XAxis type="number" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
            <YAxis type="category" dataKey="dominio_tecnologico" interval={0} tick={<CategoryAxisTick maxLength={22} />} width={145} />
            <RechartsTooltip content={<CustomTooltip />} />
            <Bar dataKey="adopcion" name="Adopción" fill="var(--observations)" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export const QualitySummaryPieChart = ({ data }) => {
  const completionRate = toNumber(data?.completion_rate);
  const chartData = [
    { name: 'Aptos (Staging)', value: completionRate },
    { name: 'Merma (Errores)', value: toNumber(data?.overall_error_rate) }
  ];

  const title = 'Completitud de la carga';
  const description = 'Contrasta el porcentaje de registros aptos en Staging con la merma provocada por las reglas de limpieza. Un porcentaje verde mayor implica mejor aprovechamiento de la carga.';
  if (!chartData.some(item => item.value > 0)) return <EmptyChart title={title} description={description} />;

  return (
    <div className="panel chart-panel quality-chart-panel">
      <h2>{title}</h2>
      <ChartDescription>{description}</ChartDescription>
      <div className="chart-body">
        <ResponsiveContainer>
          <PieChart>
            <Pie data={chartData} cx="50%" cy="48%" innerRadius={72} outerRadius={108} dataKey="value" nameKey="name" stroke="none">
              <Cell fill="var(--success)" />
              <Cell fill="var(--danger)" />
              <Label value={`${completionRate.toLocaleString('es-EC', { maximumFractionDigits: 2 })}%`} position="center" fill="var(--text-primary)" fontSize={24} fontWeight={750} />
            </Pie>
            <RechartsTooltip content={<CustomTooltip />} />
            <Legend verticalAlign="bottom" iconType="circle" />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export const QualityDedupBarChart = ({ data }) => {
  const title = 'Tasa de depuración por fuente';
  const description = 'Indica qué porcentaje de registros fue removido por duplicidad en cada fuente. Una barra más larga señala mayor repetición y necesidad de depuración.';
  const chartData = (data || [])
    .map(item => {
      const removed = toNumber(item.total_removed);
      const kept = toNumber(item.total_kept);
      const processed = removed + kept;
      return {
        ...item,
        source_label: QUALITY_SOURCE_LABELS[item.source] || item.source,
        duplicate_rate: processed > 0 ? (removed / processed) * 100 : 0
      };
    })
    .sort((a, b) => a.duplicate_rate - b.duplicate_rate);

  if (chartData.length === 0) return <EmptyChart title={title} description={description} />;

  return (
    <div className="panel chart-panel quality-chart-panel">
      <h2>{title}</h2>
      <ChartDescription>{description}</ChartDescription>
      <div className="chart-body">
        <ResponsiveContainer>
          <BarChart data={chartData} layout="vertical" margin={{ top: 12, right: 24, left: 8, bottom: 12 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border-primary)" />
            <XAxis type="number" domain={[0, 100]} tickFormatter={value => `${value}%`} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
            <YAxis type="category" dataKey="source_label" interval={0} tick={<CategoryAxisTick maxLength={17} />} width={105} />
            <RechartsTooltip content={<CustomTooltip />} />
            <Bar dataKey="duplicate_rate" name="Registros removidos (%)" fill="var(--warning)" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export const AgenteMesHeatMap = ({ data }) => {
  const description = 'Cruza agentes y meses mediante intensidad de color. Las celdas más oscuras representan una mayor adopción del agente en ese periodo.';
  if (!data || data.length === 0) {
    return (
      <div className="panel chart-panel-lg">
        <h2>Mapa de Calor: Agentes × Meses</h2>
        <ChartDescription>{description}</ChartDescription>
        <p className="no-data-message">No hay datos de matriz de cobertura disponibles.</p>
      </div>
    );
  }

  const monthOrder = {
    enero: 1, febrero: 2, marzo: 3, abril: 4, mayo: 5, junio: 6,
    julio: 7, agosto: 8, septiembre: 9, octubre: 10, noviembre: 11, diciembre: 12
  };
  const monthMap = new Map();
  data.forEach(item => {
    const monthNumber = toNumber(item.mes) || monthOrder[String(item.nombre_mes).toLowerCase()] || 0;
    const year = toNumber(item.anio);
    const key = `${year}-${monthNumber}`;
    if (!monthMap.has(key)) {
      monthMap.set(key, { key, year, monthNumber, label: `${item.nombre_mes} ${item.anio}` });
    }
  });
  const months = [...monthMap.values()].sort((a, b) => a.year - b.year || a.monthNumber - b.monthNumber);

  const agentTotals = new Map();
  data.forEach(item => {
    agentTotals.set(item.nombre_agente, (agentTotals.get(item.nombre_agente) || 0) + toNumber(item.adopcion));
  });
  const agents = [...agentTotals.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 20)
    .map(([agent]) => agent);

  const values = data.map(item => toNumber(item.adopcion));
  const maxVal = Math.max(...values, 1);

  const getColor = (val) => {
    if (val <= 0) return 'var(--heatmap-empty)';
    const opacity = 0.14 + (val / maxVal) * 0.76;
    return `rgba(53, 106, 230, ${opacity.toFixed(2)})`;
  };

  const getCellData = (agent, month) => {
    return data.find(item => {
      const itemMonth = toNumber(item.mes) || monthOrder[String(item.nombre_mes).toLowerCase()] || 0;
      return item.nombre_agente === agent && toNumber(item.anio) === month.year && itemMonth === month.monthNumber;
    });
  };

  return (
    <div className="panel chart-panel-lg">
      <h2>Mapa de Calor: Agentes × Meses (Adopción)</h2>
      <ChartDescription>{description}</ChartDescription>
      <div className="heatmap-wrapper">
        <div className="heatmap-grid" style={{ gridTemplateColumns: `140px repeat(${months.length}, 1fr)` }}>
          <div className="heatmap-corner">Agente \ Mes</div>
          {months.map(month => <div key={month.key} className="heatmap-header heatmap-cell">{month.label}</div>)}
          {agents.map(agent => (
            <React.Fragment key={agent}>
              <div className="heatmap-row-label heatmap-cell">{agent}</div>
              {months.map(month => {
                const cell = getCellData(agent, month);
                const val = toNumber(cell?.adopcion);
                return (
                  <div
                    key={`${agent}-${month.key}`}
                    className="heatmap-cell heatmap-data-cell"
                    style={{ backgroundColor: getColor(val) }}
                    title={`${agent} — ${month.label}: ${val.toLocaleString()}`}
                  >
                    <span className="heatmap-cell-value">{val > 0 ? val.toLocaleString() : ''}</span>
                  </div>
                );
              })}
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>
  );
};
