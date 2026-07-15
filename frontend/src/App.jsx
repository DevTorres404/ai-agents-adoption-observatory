import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Activity, Users, Database, TrendingUp, Cpu, ShieldCheck, AlertCircle, CalendarClock, CopyCheck, Info } from 'lucide-react';
import { fetchKpiData } from './services/api';
import GlobalFilters from './components/GlobalFilters';
import Sidebar from './components/Sidebar';
import TendenciasDashboard from './components/TendenciasDashboard';
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
  QualityDedupBarChart
} from './components/charts/Charts';
import './index.css';

const TAB_MAP = { '/': 'analytics', '/dimensiones': 'dimensiones', '/calidad': 'quality', '/tendencias': 'tendencias', '/ejecutivo': 'ejecutivo' };
const REV_TAB_MAP = { analytics: '/', dimensiones: '/dimensiones', quality: '/calidad', tendencias: '/tendencias', ejecutivo: '/ejecutivo' };
const PAGE_META = {
  ejecutivo: {
    eyebrow: 'Visión ejecutiva',
    title: 'Radar de mercado',
    description: 'Resume liderazgo, alcance y posicionamiento competitivo de los agentes de IA.',
    purpose: 'Identifica quién lidera el mercado y dónde se concentra la oportunidad.'
  },
  analytics: {
    eyebrow: 'Análisis principal',
    title: 'Analítica general',
    description: 'Compara adopción, popularidad, participación y detalle de cada agente.',
    purpose: 'Permite pasar del indicador general a las causas y registros que explican el desempeño.'
  },
  dimensiones: {
    eyebrow: 'Modelo analítico',
    title: 'Dimensiones',
    description: 'Desglosa categorías, tecnologías, comunidad, innovación y actividad.',
    purpose: 'Explica qué capacidades y señales del ecosistema impulsan la adopción.'
  },
  tendencias: {
    eyebrow: 'Evolución temporal',
    title: 'Tendencias',
    description: 'Muestra cambios mensuales, fuentes dominantes y comportamiento por agente.',
    purpose: 'Distingue crecimiento sostenido de picos provocados por una fuente o carga puntual.'
  },
  quality: {
    eyebrow: 'Gobierno de datos',
    title: 'Calidad de datos',
    description: 'Audita la carga Raw–Staging, los duplicados y los registros aptos para análisis.',
    purpose: 'Confirma si la información es confiable y cuánto volumen fue depurado o descartado.'
  }
};

const SOURCE_LABELS = {
  arxiv: 'arXiv',
  catalogo: 'Catálogo',
  devto: 'Dev.to',
  fuente_propia: 'Fuente propia',
  github: 'GitHub',
  gnews: 'Google News',
  google_trends: 'Google Trends',
  hackernews: 'Hacker News',
  reddit: 'Reddit',
  stackoverflow: 'Stack Overflow'
};

const formatSourceLabel = source => SOURCE_LABELS[source] || source || 'Sin fuente';

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

  const handleApplyFilters = useCallback(newFilters => { setFilters(newFilters); }, []);
  const handleClearFilters = useCallback(() => { setFilters({}); }, []);
  const handleViewDataset = useCallback(() => {
    navigate('/');
    window.setTimeout(() => document.getElementById('dataset-table')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 120);
  }, [navigate]);

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

  const executionDate = quality?.summary?.execution_date;
  const headerUpdateLabel = executionDate
    ? new Date(executionDate.endsWith('Z') ? executionDate : `${executionDate}Z`).toLocaleDateString('es-EC', {
        day: '2-digit', month: 'short', year: 'numeric', timeZone: 'America/Guayaquil'
      }).replace('.', '')
    : null;

  const qualityExecutionLabel = executionDate
    ? new Date(executionDate.endsWith('Z') ? executionDate : `${executionDate}Z`).toLocaleString('es-EC', {
        day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'America/Guayaquil'
      }).replace('.', '')
    : 'Sin ejecución registrada';

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
        />
        <div className="app-main">
          <header className="content-header">
            <div>
              <span className="page-eyebrow">{pageMeta.eyebrow}</span>
              <h1>{pageMeta.title}</h1>
              <p>{pageMeta.description}</p>
              <div className="page-purpose"><Info size={14} /><span><strong>Lectura clave:</strong> {pageMeta.purpose}</span></div>
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
      />
      <div className="app-main">
        <header className="content-header">
          <div>
            <span className="page-eyebrow">{pageMeta.eyebrow}</span>
            <h1>{pageMeta.title}</h1>
            <p>{pageMeta.description}</p>
            <div className="page-purpose"><Info size={14} /><span><strong>Lectura clave:</strong> {pageMeta.purpose}</span></div>
          </div>
          <div className={`refresh-status ${apiErrors.length ? 'has-errors' : ''}`}>
            {refreshing ? <span className="spinner spinner-small" /> : <span className="refresh-dot" />}
            {refreshing
              ? 'Actualizando datos'
              : apiErrors.length
                ? 'Datos incompletos'
                : activeTab === 'tendencias' && headerUpdateLabel
                  ? `Actualizado: ${headerUpdateLabel}`
                  : 'Datos actualizados'}
          </div>
        </header>

        <main className="dashboard-content">
        {activeTab !== 'quality' && (
          <GlobalFilters
            currentFilters={filters}
            onApplyFilters={handleApplyFilters}
            onClearFilters={handleClearFilters}
            onViewDataset={handleViewDataset}
          />
        )}

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

              <div id="dataset-table" className="panel" style={{ height: '450px', overflowY: 'auto' }}>
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
          <TendenciasDashboard data={data} filters={filters} />
        )}
        </ErrorBoundary>

        <ErrorBoundary name="Calidad tab">
        {data && activeTab === 'quality' && (
          <div className="quality-dashboard">
            <section className="panel quality-run-strip" aria-label="Estado de la auditoría">
              <div className="quality-run-summary">
                <span className="quality-run-icon"><ShieldCheck size={20} /></span>
                <div>
                  <strong>Auditoría de la carga actual</strong>
                  <span>Resumen consolidado del último procesamiento ETL.</span>
                </div>
              </div>
              <div className="quality-run-meta">
                <div>
                  <CalendarClock size={17} />
                  <span><small>Última ejecución</small><strong>{qualityExecutionLabel}</strong></span>
                </div>
                <div>
                  <Database size={17} />
                  <span><small>Fuentes auditadas</small><strong>{quality?.dedup?.length || 0}</strong></span>
                </div>
                <span className="quality-status-chip"><ShieldCheck size={15} /> Validación completada</span>
              </div>
            </section>

            <div className="quality-kpi-grid">
              <KPICard title="Registros Raw Extraídos" value={quality?.summary?.total_raw_records?.toLocaleString() || 0} subtext="Datos crudos pre-limpieza" icon={Database} color="var(--info)" />
              <KPICard title="Registros Staging Aptos" value={quality?.summary?.total_staging_records?.toLocaleString() || 0} subtext="Datos limpios insertados en Gold" icon={ShieldCheck} color="var(--success)" />
              <KPICard title="Tasa de Completitud" value={`${Number(quality?.summary?.completion_rate || 0).toLocaleString('es-EC', { maximumFractionDigits: 2 })} %`} subtext="Porcentaje apto para análisis" icon={Activity} color="var(--primary)" />
              <KPICard title="Duplicados Removidos" value={quality?.summary?.total_duplicates_removed?.toLocaleString() || 0} subtext="Registros depurados en la carga" icon={CopyCheck} color="var(--warning)" />
              <KPICard title="Nulos Críticos" value={quality?.summary?.total_nulls_removed ?? 0} subtext="Descartados por campos críticos" icon={AlertCircle} color={(quality?.summary?.total_nulls_removed || 0) === 0 ? 'var(--success)' : 'var(--danger)'} />
            </div>

            <div className="quality-visual-grid">
              {quality?.summary && <QualitySummaryPieChart data={quality.summary} />}
              {quality?.dedup && <QualityDedupBarChart data={quality.dedup} />}
            </div>

              <div className="panel quality-table-panel">
                <h2>Auditoría de Duplicados por Fuente</h2>
                <div className="table-responsive">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Fuente</th>
                        <th>Procesados</th>
                        <th>Removidos</th>
                        <th>Aprobados</th>
                        <th>Tasa de depuración</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(quality?.dedup || []).map((item, i) => {
                        const removed = Number(item.total_removed) || 0;
                        const kept = Number(item.total_kept) || 0;
                        const processed = removed + kept;
                        const removalRate = processed > 0 ? (removed / processed) * 100 : 0;
                        return (
                          <tr key={i}>
                            <td style={{ fontWeight: 600 }}>{formatSourceLabel(item.source)}</td>
                            <td className="status-info">{processed.toLocaleString()}</td>
                            <td className="status-warning">{removed.toLocaleString()}</td>
                            <td className="status-success">{kept.toLocaleString()}</td>
                            <td><span className="quality-rate-badge">{removalRate.toLocaleString('es-EC', { maximumFractionDigits: 1 })} %</span></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
          </div>
        )}
        </ErrorBoundary>

        </main>
      </div>
    </div>
  );
}

export default App;
