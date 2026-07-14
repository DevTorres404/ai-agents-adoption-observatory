import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Activity, Users, Database, TrendingUp, Cpu, ShieldCheck, AlertCircle } from 'lucide-react';
import { fetchKpiData } from './services/api';
import GlobalFilters from './components/GlobalFilters';
import Sidebar from './components/Sidebar';
import { KPICard } from './components/KPI';
import { ErrorBoundary } from './components/ErrorBoundary';
import {
  RankingBarChart,
  TendenciaLineChart,
  FuenteBarChart,
  ComparadorAgentesChart,
  PosicionamientoScatterChart,
  CategoriaPieChart,
  TecnologiaBarChart,
  QualitySummaryPieChart,
  QualityDedupBarChart,
  AgenteMesHeatMap
} from './components/charts/Charts';
import './index.css';

const TAB_MAP = { '/': 'analytics', '/dimensiones': 'dimensiones', '/calidad': 'quality', '/tendencias': 'tendencias', '/ejecutivo': 'ejecutivo' };
const REV_TAB_MAP = { analytics: '/', dimensiones: '/dimensiones', quality: '/calidad', tendencias: '/tendencias', ejecutivo: '/ejecutivo' };
const PAGE_META = {
  ejecutivo: { eyebrow: 'Visión ejecutiva', title: 'Radar de mercado', description: 'Señales clave de presencia, adopción e innovación en el ecosistema de agentes de IA.' },
  analytics: { eyebrow: 'Análisis principal', title: 'Analítica general', description: 'Desempeño agregado, comparativas y detalle de los agentes identificados.' },
  dimensiones: { eyebrow: 'Modelo analítico', title: 'Dimensiones', description: 'Explora categorías, tecnologías, comunidad, innovación y actividad.' },
  tendencias: { eyebrow: 'Evolución temporal', title: 'Tendencias', description: 'Comportamiento mensual de la adopción y el volumen de observaciones.' },
  quality: { eyebrow: 'Gobierno de datos', title: 'Calidad de datos', description: 'Trazabilidad del procesamiento, duplicados y registros aptos para análisis.' }
};

function computeTrend(data, metricKey) {
  if (!data || data.length < 2) return null;
  const sorted = [...data].sort((a, b) => a.anio - b.anio || a.mes - b.mes);
  const last = sorted[sorted.length - 1];
  const prev = sorted[sorted.length - 2];
  if (!last || !prev) return null;
  const lastVal = Number(last[metricKey]) || 0;
  const prevVal = Number(prev[metricKey]) || 0;
  if (prevVal === 0) return null;
  return {
    value: ((lastVal - prevVal) / prevVal) * 100,
    isPositive: lastVal >= prevVal,
    label: 'Variación vs mes anterior'
  };
}

function SkeletonCards() {
  return (
    <div className="grid-cards">
      {[1, 2, 3].map(i => <div key={i} className="panel skeleton skeleton-card" />)}
    </div>
  );
}

function SkeletonCharts() {
  return (
    <div className="grid-charts">
      {[1, 2].map(i => <div key={i} className="panel skeleton skeleton-chart" />)}
    </div>
  );
}

function ErrorBanner({ message }) {
  if (!message) return null;
  return (
    <div className="error-banner">
      <AlertCircle size={18} />
      {message}
    </div>
  );
}

function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const activeTab = TAB_MAP[location.pathname] || 'analytics';

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [apiErrors, setApiErrors] = useState([]);
  const [filters, setFilters] = useState({});
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('dashboard-theme') || 'light';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('dashboard-theme', theme);
  }, [theme]);

  useEffect(() => {
    if (!Object.prototype.hasOwnProperty.call(TAB_MAP, location.pathname)) {
      navigate('/', { replace: true });
    }
  }, [location.pathname, navigate]);

  const toggleTheme = () => setTheme(prev => prev === 'light' ? 'dark' : 'light');

  const handleTabChange = (tab) => {
    navigate(REV_TAB_MAP[tab]);
    setIsSidebarOpen(false);
  };

  const loadData = useCallback(async (currentFilters) => {
    setLoading(true);
    setRefreshing(true);
    setApiErrors([]);
    try {
      const apiFilters = { ...currentFilters };
      const result = await fetchKpiData(apiFilters);
      setData(result);
      if (result._apiErrors && result._apiErrors.length > 0) {
        setApiErrors(result._apiErrors);
      }
    } catch (err) {
      setApiErrors([err.message || 'Error al conectar con el backend']);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData(filters);
  }, [filters, loadData]);

  const handleApplyFilters = (newFilters) => { setFilters(newFilters); };
  const handleClearFilters = () => { setFilters({}); };

  const totalAgentes = data?.ranking?.length || 0;

  const totalObservaciones = useMemo(() => {
    return data?.distribucion?.reduce((acc, curr) => acc + (Number(curr.total_observaciones) || 0), 0) || 0;
  }, [data]);

  const topAgente = data?.ranking?.[0] || { nombre_agente: 'Sin datos', categoria_agente: '-' };

  const adopcionTrend = useMemo(() => {
    if (!data?.tendencia) return null;
    return computeTrend(data.tendencia, 'suma_adopcion');
  }, [data]);

  const observacionesTrend = useMemo(() => {
    if (!data?.tendencia) return null;
    return computeTrend(data.tendencia, 'total_observaciones');
  }, [data]);

  const quality = data ? {
    summary: data.qualitySummary,
    dedup: data.qualityDedup,
    nulls: data.qualityNulls
  } : null;

  const mainApiError = apiErrors.length > 0
    ? `${apiErrors.length} endpoint(s) fallaron. Los datos pueden estar incompletos.`
    : null;

  const pageMeta = PAGE_META[activeTab];

  if (loading && !data) {
    return (
      <div className="dashboard-container">
        <Sidebar
          activeTab={activeTab}
          onNavigate={handleTabChange}
          theme={theme}
          onToggleTheme={toggleTheme}
          isOpen={isSidebarOpen}
          onOpen={() => setIsSidebarOpen(true)}
          onClose={() => setIsSidebarOpen(false)}
          refreshing
          hasErrors={false}
        />
        <div className="app-main">
          <header className="content-header">
            <div>
              <span className="page-eyebrow">{pageMeta.eyebrow}</span>
              <h1>{pageMeta.title}</h1>
              <p>{pageMeta.description}</p>
            </div>
            <div className="refresh-status"><span className="spinner spinner-small" /> Preparando datos</div>
          </header>
          <main className="dashboard-content">
            <div className="panel skeleton skeleton-card" style={{ height: '80px' }} />
            <SkeletonCards />
            <SkeletonCharts />
          </main>
        </div>
      </div>
    );
  }

  const rankedData = data?.ranking ? [...data.ranking].sort((a, b) => (b.adopcion || 0) - (a.adopcion || 0)) : [];

  return (
    <div className="dashboard-container">
      <Sidebar
        activeTab={activeTab}
        onNavigate={handleTabChange}
        theme={theme}
        onToggleTheme={toggleTheme}
        isOpen={isSidebarOpen}
        onOpen={() => setIsSidebarOpen(true)}
        onClose={() => setIsSidebarOpen(false)}
        refreshing={refreshing}
        hasErrors={apiErrors.length > 0}
      />
      <div className="app-main">
        <header className="content-header">
          <div>
            <span className="page-eyebrow">{pageMeta.eyebrow}</span>
            <h1>{pageMeta.title}</h1>
            <p>{pageMeta.description}</p>
          </div>
          <div className={`refresh-status ${apiErrors.length ? 'has-errors' : ''}`}>
            {refreshing ? <span className="spinner spinner-small" /> : <span className="refresh-dot" />}
            {refreshing ? 'Actualizando datos' : apiErrors.length ? 'Datos incompletos' : 'Datos actualizados'}
          </div>
        </header>

        <main className="dashboard-content">
        <GlobalFilters
          currentFilters={filters}
          onApplyFilters={handleApplyFilters}
          onClearFilters={handleClearFilters}
        />

        {mainApiError && <ErrorBanner message={mainApiError} />}

        {loading && data && (
          <div style={{ opacity: 0.5, pointerEvents: 'none', position: 'relative' }}>
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 10 }}>
              <div className="spinner" />
            </div>
          </div>
        )}

        <ErrorBoundary name="Ejecutivo tab">
        {data && activeTab === 'ejecutivo' && (
          <>
            <div className="grid-cards">
              <KPICard title="Total Menciones Globales" value={data.ranking?.reduce((sum, item) => sum + (item.total_menciones || 0), 0).toLocaleString() || 0} subtext="Impacto total en todas las fuentes" icon={TrendingUp} color="var(--mentions)" />
              <KPICard title="Líder Absoluto" value={topAgente.nombre_agente} subtext={`Score Adopción: ${topAgente.adopcion?.toLocaleString()}`} icon={Activity} color="var(--primary)" />
              <KPICard title="Innovador Destacado" value={data.ranking ? [...data.ranking].sort((a,b) => (b.innovacion||0) - (a.innovacion||0))[0]?.nombre_agente || '-' : '-'} subtext="Mayor puntaje de innovación" icon={Cpu} color="var(--accent)" />
            </div>

            <div className="grid-charts">
              <PosicionamientoScatterChart data={data.ranking || []} />
              <RankingBarChart data={data.ranking ? [...data.ranking].sort((a,b) => (b.popularidad||0) - (a.popularidad||0)).slice(0, 10).reverse() : []} metric="popularidad" title="Top 10 Agentes más Populares" color="var(--secondary)" />
              <TendenciaLineChart data={data.tendencia || []} metricKey="suma_adopcion" metricName="Evolución del Share of Voice (Adopción)" color="var(--mentions)" />
            </div>
          </>
        )}
        </ErrorBoundary>

        <ErrorBoundary name="Analytics tab">
        {data && activeTab === 'analytics' && (
          <>
            <div className="grid-cards">
              <KPICard title="Total Observaciones" value={totalObservaciones.toLocaleString()} subtext="Datasets procesados en Gold" icon={Database} color="var(--observations)" trend={observacionesTrend} />
              <KPICard title="Agentes Identificados" value={totalAgentes} subtext="Excluyendo no identificados" icon={Users} color="var(--secondary)" sparklineData={data.tendencia} sparklineDataKey="suma_adopcion" trend={adopcionTrend} />
              <KPICard title="Líder Global (Adopción)" value={topAgente.nombre_agente} subtext={topAgente.categoria_agente} icon={Activity} color="var(--primary)" />
            </div>

            <div className="grid-charts">
              <RankingBarChart data={[...rankedData].reverse()} metric="adopcion" title="Score de Adopción" color="var(--primary)" />
              <TendenciaLineChart data={data.tendencia || []} metricKey="suma_adopcion" metricName="Score Adopción" color="var(--primary)" />
              <ComparadorAgentesChart data={data.ranking?.slice(0, 5) || []} />
              <FuenteBarChart data={data.participacion || []} />

              <div className="panel" style={{ height: '450px', overflowY: 'auto' }}>
                <h2>Tabla Analítica Detallada</h2>
                <div className="table-responsive">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Agente</th>
                        <th>Categoría</th>
                        <th>Obs.</th>
                        <th>Adopción</th>
                        <th>Popularidad</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rankedData.map((item, i) => (
                        <tr key={i}>
                          <td style={{ fontWeight: 600, color: 'var(--primary)' }}>{item.nombre_agente}</td>
                          <td>{item.categoria_agente}</td>
                          <td>{item.total_observaciones?.toLocaleString()}</td>
                          <td>{item.adopcion?.toLocaleString()}</td>
                          <td>{item.popularidad?.toLocaleString()}</td>
                        </tr>
                      ))}
                      {rankedData.length === 0 && (
                        <tr><td colSpan="5" style={{ textAlign: 'center', padding: '2rem' }}>No existen datos para los filtros seleccionados.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </>
        )}
        </ErrorBoundary>

        <ErrorBoundary name="Dimensiones tab">
        {data && activeTab === 'dimensiones' && (
          <div className="grid-charts">
            <CategoriaPieChart data={data.categorias || []} />
            <TecnologiaBarChart data={data.tecnologias || []} />
            <RankingBarChart data={[...rankedData].sort((a, b) => (b.comunidad || 0) - (a.comunidad || 0)).reverse()} metric="comunidad" title="Score de Comunidad" color="var(--mentions)" />
            <RankingBarChart data={[...rankedData].sort((a, b) => (b.innovacion || 0) - (a.innovacion || 0)).reverse()} metric="innovacion" title="Score de Innovación" color="var(--accent)" />
            <RankingBarChart data={[...rankedData].sort((a, b) => (b.actividad || 0) - (a.actividad || 0)).reverse()} metric="actividad" title="Score de Actividad" color="var(--interactions)" />
          </div>
        )}
        </ErrorBoundary>

        <ErrorBoundary name="Tendencias tab">
        {data && activeTab === 'tendencias' && (
          <div className="grid-charts">
            <TendenciaLineChart data={data.tendencia || []} metricKey="suma_adopcion" metricName="Score Adopción" color="var(--primary)" />
            <TendenciaLineChart data={data.tendencia || []} metricKey="total_observaciones" metricName="Total Observaciones" color="var(--observations)" />
            <AgenteMesHeatMap data={data.tendenciaAgentes || []} />
          </div>
        )}
        </ErrorBoundary>

        <ErrorBoundary name="Calidad ETL tab">
        {data && activeTab === 'quality' && (
          <>
            <div className="grid-cards">
              <KPICard title="Registros Raw Extraídos" value={quality?.summary?.total_raw_records?.toLocaleString() || 0} subtext="Datos crudos pre-limpieza" icon={Database} color="var(--info)" />
              <KPICard title="Registros Staging Aptos" value={quality?.summary?.total_staging_records?.toLocaleString() || 0} subtext="Datos limpios insertados en Gold" icon={ShieldCheck} color="var(--success)" />
              <KPICard title="Nulos Críticos" value={quality?.summary?.total_nulls_removed ?? 0} subtext="Registros descartados por faltar datos" icon={AlertCircle} color="var(--danger)" />
            </div>

            <div className="grid-charts">
              {quality?.summary && <QualitySummaryPieChart data={quality.summary} />}
              {quality?.dedup && <QualityDedupBarChart data={quality.dedup} />}

              <div className="panel" style={{ height: '400px', overflowY: 'auto' }}>
                <h2>Auditoría de Duplicados por Fuente</h2>
                <div className="table-responsive">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Fuente</th>
                        <th>Detectados</th>
                        <th>Removidos</th>
                        <th>Aprobados</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(quality?.dedup || []).map((item, i) => (
                        <tr key={i}>
                          <td style={{ fontWeight: 600 }}>{item.source}</td>
                          <td className="status-info">{item.total_detected?.toLocaleString()}</td>
                          <td className="status-warning">{item.total_removed?.toLocaleString()}</td>
                          <td className="status-success">{item.total_kept?.toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </>
        )}
        </ErrorBoundary>

        </main>
      </div>
    </div>
  );
}

export default App;
