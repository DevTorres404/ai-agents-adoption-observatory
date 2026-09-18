import React, { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ShieldCheck, AlertCircle, CalendarClock, CopyCheck, Info, Activity, Database } from 'lucide-react';
import { fetchKpiData } from './services/api';
import { formatSourceLabel } from './utils/labels';
import GlobalFilters from './components/GlobalFilters';
import Sidebar from './components/Sidebar';
import TendenciasDashboard from './components/TendenciasDashboard';
import EjecutivoDashboard from './components/EjecutivoDashboard';
import { ErrorBoundary } from './components/ErrorBoundary';
import { KPICard } from './components/KPI';
import {
  RankingBarChart,
  CategoriaPieChart,
  TecnologiaBarChart,
  QualitySummaryPieChart
} from './components/charts/Charts';
import './index.css';


const TAB_MAP = { '/': 'ejecutivo', '/dimensiones': 'dimensiones', '/calidad': 'quality', '/tendencias': 'tendencias', '/ejecutivo': 'ejecutivo' };
const REV_TAB_MAP = { ejecutivo: '/', dimensiones: '/dimensiones', quality: '/calidad', tendencias: '/tendencias' };
const PAGE_META = {
  ejecutivo: {
    eyebrow: 'Visión ejecutiva',
    title: 'Radar de mercado',
    description: 'Resume liderazgo, alcance y posicionamiento competitivo de los agentes de IA.',
    purpose: 'Identifica quién lidera el mercado y dónde se concentra la oportunidad.'
  },
  dimensiones: {
    eyebrow: 'Modelo analítico',
    title: 'Dimensiones y detalle',
    description: 'Desglose por categoría, tecnología, fuente, comunidad, innovación y tabla de agentes.',
    purpose: 'Explica qué capacidades y señales del ecosistema impulsan la adopción, con acceso al registro individual.'
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
  const [communityOnly, setCommunityOnly] = useState(false);
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



  const quality = data ? {
    summary: data.qualitySummary,
    dedup: data.qualityDedup,
    nulls: data.qualityNulls
  } : null;

  const executionDate = quality?.summary?.execution_date;
  // Convención del proyecto: timestamps naive = America/Guayaquil (UTC-5, sin DST).
  const parseExecutionDate = (value) => {
    if (!value) return null;
    if (/Z$|[+-]\d{2}:\d{2}$/.test(value)) return new Date(value);
    return new Date(`${value}-05:00`);
  };
  const headerUpdateLabel = executionDate
    ? parseExecutionDate(executionDate).toLocaleDateString('es-EC', {
        day: '2-digit', month: 'short', year: 'numeric', timeZone: 'America/Guayaquil'
      }).replace('.', '')
    : null;

  const qualityExecutionLabel = executionDate
    ? parseExecutionDate(executionDate).toLocaleString('es-EC', {
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
            refreshing={refreshing}
          />
        )}

        {mainApiError && <ErrorBanner message={mainApiError} />}

        {loading && data && (
          <div style={{ opacity: 0.5, pointerEvents: 'none', position: 'relative' }} role="status" aria-live="polite">
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 10 }}>
              <div className="spinner" />
            </div>
          </div>
        )}

        <ErrorBoundary name="Ejecutivo tab">
        {data && activeTab === 'ejecutivo' && (
          <EjecutivoDashboard data={data} />
        )}
        </ErrorBoundary>


        <ErrorBoundary name="Dimensiones tab">
        {data && activeTab === 'dimensiones' && (
          <div className="grid-charts">
            <CategoriaPieChart data={data.categorias || []} />
            <TecnologiaBarChart data={data.tecnologias || []} />
            <RankingBarChart data={[...rankedData].reverse()} metric="adopcion" title="Score de Adopción" color="var(--primary)" />

            <div id="dataset-table" className="panel" style={{ height: '450px', overflowY: 'auto' }}>
              <h2>Tabla Analítica Detallada</h2>
              <p className="chart-description">
                Registro individual del agregado completo de agentes (más de un top-N): observaciones, score de adopción y popularidad acumulados del período. El score de adopción es la suma de contribuciones normalizadas por fuente, no un porcentaje.
              </p>
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
        )}
        </ErrorBoundary>

        <ErrorBoundary name="Tendencias tab">
        {data && activeTab === 'tendencias' && (
          <TendenciasDashboard data={data} filters={filters} communityOnly={communityOnly} onToggleCommunity={setCommunityOnly} />
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
              <KPICard title="Registros Raw Extraídos" value={quality?.summary?.total_raw_records?.toLocaleString() || 0} subtext="Registros crudos antes de la limpieza ETL" icon={Database} color="var(--info)" />
              <KPICard title="Registros Staging Aptos" value={quality?.summary?.total_staging_records?.toLocaleString() || 0} subtext="Registros que superaron limpieza y deduplicación" icon={ShieldCheck} color="var(--success)" />
              <KPICard title="Tasa de Completitud" value={`${Number(quality?.summary?.completion_rate || 0).toLocaleString('es-EC', { maximumFractionDigits: 2 })} %`} subtext="Aptos sobre el total extraído; mide campos críticos, no calidad global" icon={Activity} color="var(--primary)" />
              <KPICard title="Duplicados Removidos" value={quality?.summary?.total_duplicates_removed?.toLocaleString() || 0} subtext="Registros descartados por duplicidad en el ETL" icon={CopyCheck} color="var(--warning)" />
              <KPICard title="Nulos Críticos" value={quality?.summary?.total_nulls_removed ?? 0} subtext="Descartados por campos críticos vacíos" icon={AlertCircle} color={(quality?.summary?.total_nulls_removed || 0) === 0 ? 'var(--success)' : 'var(--danger)'} />
            </div>

            {quality?.summary && <QualitySummaryPieChart data={quality.summary} />}

              <div className="panel quality-table-panel">
                <h2>Auditoría de Duplicados por Fuente</h2>
                <p className="chart-description">
                  Detalle por fuente de los registros procesados, removidos por duplicidad y aprobados. La tasa de depuración es removidos / procesados, en porcentaje.
                </p>
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

              {data.governance?.freshness?.length > 0 && (
                <div className="panel quality-table-panel">
                  <h2>Frescura por Fuente</h2>
                  <p className="chart-description">
                    Antigüedad de la última extracción exitosa por fuente. Una fuente se marca desactualizada cuando supera el umbral de frescura configurado.
                  </p>
                  <div className="table-responsive">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Fuente</th>
                          <th>Último intento</th>
                          <th>Último éxito</th>
                          <th>Antigüedad (h)</th>
                          <th>Estado</th>
                          <th>Registros extraídos</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.governance.freshness.map((item, i) => (
                          <tr key={i}>
                            <td style={{ fontWeight: 600 }}>{formatSourceLabel(item.source)}</td>
                            <td>{item.last_attempt_at ? new Date(item.last_attempt_at).toLocaleString('es-EC') : '—'}</td>
                            <td>{item.last_success_at ? new Date(item.last_success_at).toLocaleString('es-EC') : '—'}</td>
                            <td>{item.age_hours != null ? Number(item.age_hours).toFixed(1) : '—'}</td>
                            <td>
                              <span className={item.is_stale ? 'quality-rate-badge status-warning' : 'quality-rate-badge status-success'}>
                                {item.is_stale ? '⚠ Desactualizada' : '✓ Fresca'}
                              </span>
                            </td>
                            <td className="status-info">{Number(item.records_extracted || 0).toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {data.governance?.coverage?.length > 0 && (
                <div className="panel quality-table-panel">
                  <h2>Cobertura Semántica por Fuente</h2>
                  <p className="chart-description">
                    Porcentaje de registros con la dimensión semántica completa (categoría, tecnología o plataforma) frente al total por fuente. El umbral indica el mínimo aceptable.
                  </p>
                  <div className="table-responsive">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Fuente</th>
                          <th>Dimensión</th>
                          <th>Cubiertos</th>
                          <th>Total</th>
                          <th>Cobertura</th>
                          <th>Umbral</th>
                          <th>Estado</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.governance.coverage.map((item, i) => (
                          <tr key={i}>
                            <td style={{ fontWeight: 600 }}>{formatSourceLabel(item.source)}</td>
                            <td style={{ textTransform: 'capitalize' }}>{item.dimension}</td>
                            <td>{Number(item.covered_count || 0).toLocaleString()}</td>
                            <td>{Number(item.total_count || 0).toLocaleString()}</td>
                            <td>
                              <span className={item.warning ? 'quality-rate-badge status-warning' : 'quality-rate-badge status-success'}>
                                {Number(item.coverage_pct || 0).toFixed(1)} %
                              </span>
                            </td>
                            <td>{Number(item.threshold_pct || 0).toFixed(0)} %</td>
                            <td>{item.warning ? '⚠ Bajo umbral' : '✓ OK'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

          </div>
        )}
        </ErrorBoundary>

        </main>
      </div>
    </div>
  );
}

export default App;
