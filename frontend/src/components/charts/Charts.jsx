import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, AreaChart, Area, ScatterChart, Scatter, ZAxis, ReferenceLine, Legend
} from 'recharts';

const CHART_COLORS = [
  "var(--primary)", "var(--secondary)", "var(--accent)", 
  "var(--warning)", "var(--info)", "var(--neutral)"
];

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="recharts-default-tooltip">
        <p className="recharts-tooltip-label">{label}</p>
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

export const RankingBarChart = ({ data, metric, title, color }) => {
  return (
    <div className="panel chart-panel">
      <h2>{title}</h2>
      <div className="chart-body">
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ top: 10, right: 30, left: 100, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="var(--border-primary)" />
            <XAxis type="number" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
            <YAxis type="category" dataKey="nombre_agente" tick={{ fill: 'var(--text-secondary)', fontSize: 12, fontWeight: 600 }} width={90} />
            <RechartsTooltip content={<CustomTooltip />} />
            <Bar dataKey={metric} name="Puntuación" fill={color || "var(--primary)"} radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export const TendenciaLineChart = ({ data, metricKey, metricName, color }) => {
  const chartData = data.map(item => ({
    name: `${item.nombre_mes} ${item.anio}`,
    valor: item[metricKey]
  }));

  return (
    <div className="panel chart-panel">
      <h2>Evolución Temporal: {metricName}</h2>
      <div className="chart-body">
        <ResponsiveContainer>
          <AreaChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 50 }}>
            <defs>
              <linearGradient id="colorMetric" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color || "var(--primary)"} stopOpacity={0.8}/>
                <stop offset="95%" stopColor={color || "var(--primary)"} stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-primary)" />
            <XAxis dataKey="name" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} angle={-45} textAnchor="end" />
            <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
            <RechartsTooltip content={<CustomTooltip />} />
            <Area type="monotone" dataKey="valor" name={metricName} stroke={color || "var(--primary)"} fillOpacity={1} fill="url(#colorMetric)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export const ComparadorAgentesChart = ({ data }) => {
  return (
    <div className="panel chart-panel">
      <h2>Comparativa de Líderes (Adopción vs Popularidad)</h2>
      <div className="chart-body">
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 20, right: 10, left: 10, bottom: 50 }}>
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
  return (
    <div className="panel chart-panel">
      <h2>Participación por Fuente</h2>
      <div className="chart-body">
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ top: 20, right: 30, left: 120, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="var(--border-primary)" />
            <XAxis type="number" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
            <YAxis type="category" dataKey="nombre_fuente" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} width={110} />
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
  const validData = data.filter(d => d.adopcion > 0 || d.popularidad > 0);
  if (validData.length === 0) return null;
  
  const sortedAdop = [...validData].sort((a,b) => a.adopcion - b.adopcion);
  const medAdop = sortedAdop[Math.floor(sortedAdop.length/2)]?.adopcion || 0;
  
  const sortedPop = [...validData].sort((a,b) => a.popularidad - b.popularidad);
  const medPop = sortedPop[Math.floor(sortedPop.length/2)]?.popularidad || 0;

  return (
    <div className="panel chart-panel-lg">
      <h2>Posicionamiento: Adopción vs Popularidad</h2>
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
  return (
    <div className="panel chart-panel">
      <h2>Distribución por Categoría</h2>
      <div className="chart-body">
        <ResponsiveContainer>
          <PieChart>
            <Pie data={data} cx="50%" cy="50%" innerRadius={80} outerRadius={120} paddingAngle={5} dataKey="adopcion" nameKey="categoria_agente" stroke="none">
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
              ))}
            </Pie>
            <RechartsTooltip content={<CustomTooltip />} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export const TecnologiaBarChart = ({ data }) => {
  return (
    <div className="panel chart-panel">
      <h2>Adopción por Dominio Tecnológico</h2>
      <div className="chart-body">
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ top: 20, right: 30, left: 120, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="var(--border-primary)" />
            <XAxis type="number" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
            <YAxis type="category" dataKey="dominio_tecnologico" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} width={110} />
            <RechartsTooltip content={<CustomTooltip />} />
            <Bar dataKey="adopcion" name="Adopción" fill="var(--observations)" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export const QualitySummaryPieChart = ({ data }) => {
  const chartData = [
    { name: 'Aptos (Staging)', value: parseFloat(data.completion_rate) },
    { name: 'Merma (Errores)', value: parseFloat(data.overall_error_rate) }
  ];

  return (
    <div className="panel chart-panel">
      <h2>Tasa de Completitud General</h2>
      <div className="chart-body">
        <ResponsiveContainer>
          <PieChart>
            <Pie data={chartData} cx="50%" cy="50%" innerRadius={0} outerRadius={120} dataKey="value" nameKey="name" stroke="none">
              <Cell fill="var(--success)" />
              <Cell fill="var(--danger)" />
            </Pie>
            <RechartsTooltip content={<CustomTooltip />} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export const QualityDedupBarChart = ({ data }) => {
  const chartData = data.filter(d => d.total_removed > 0);
  return (
    <div className="panel chart-panel">
      <h2>Duplicados Removidos por Fuente</h2>
      <div className="chart-body">
        <ResponsiveContainer>
          <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 50 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-primary)" />
            <XAxis dataKey="source" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} angle={-45} textAnchor="end" />
            <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
            <RechartsTooltip content={<CustomTooltip />} />
            <Bar dataKey="total_removed" name="Duplicados Removidos" fill="var(--warning)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export const AgenteMesHeatMap = ({ data }) => {
  if (!data || data.length === 0) {
    return (
      <div className="panel chart-panel-lg">
        <h2>Mapa de Calor: Agentes × Meses</h2>
        <p className="no-data-message">No hay datos de matriz de cobertura disponibles.</p>
      </div>
    );
  }

  const months = [...new Set(data.map(d => `${d.nombre_mes} ${d.anio}`))];
  const agents = [...new Set(data.map(d => d.nombre_agente))].slice(0, 20);

  const values = data.flatMap(d => [d.total_observaciones, d.adopcion, d.popularidad].filter(v => v != null));
  const maxVal = Math.max(...values, 1);

  const getColor = (val) => {
    const intensity = val / maxVal;
    if (intensity === 0) return 'var(--heatmap-empty)';
    const r = Math.round(29 + (6 - 29) * intensity);
    const g = Math.round(78 + (78 - 78) * intensity);
    const b = Math.round(216 + (160 - 216) * intensity);
    return `rgb(${r}, ${g}, ${b})`;
  };

  const getCellData = (agent, month) => {
    const [mes, anio] = month.split(' ');
    return data.find(d => d.nombre_agente === agent && d.nombre_mes === mes && String(d.anio) === anio);
  };

  return (
    <div className="panel chart-panel-lg">
      <h2>Mapa de Calor: Agentes × Meses (Adopción)</h2>
      <div className="heatmap-wrapper">
        <div className="heatmap-grid" style={{ gridTemplateColumns: `140px repeat(${months.length}, 1fr)` }}>
          <div className="heatmap-corner">Agente \ Mes</div>
          {months.map(m => <div key={m} className="heatmap-header heatmap-cell">{m}</div>)}
          {agents.map(agent => (
            <React.Fragment key={agent}>
              <div className="heatmap-row-label heatmap-cell">{agent}</div>
              {months.map(month => {
                const cell = getCellData(agent, month);
                const val = cell?.adopcion || 0;
                return (
                  <div
                    key={`${agent}-${month}`}
                    className="heatmap-cell heatmap-data-cell"
                    style={{ backgroundColor: getColor(val) }}
                    title={`${agent} — ${month}: ${val.toLocaleString()}`}
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
