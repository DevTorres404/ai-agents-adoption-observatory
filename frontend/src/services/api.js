import axios from 'axios';
import { apiCache } from '../utils/cache';

const API_BASE_URL = '/api/kpi';
const CACHE_KEY = 'dashboard_data';

const endpoints = {
  adopcion: '/adopcion',
  participacion: '/participacion',
  tendencia: '/tendencia',
  tendenciaAgentes: '/tendencia/agentes',
  ranking: '/ranking',
  matriz: '/matriz_cobertura',
  popularidad: '/popularidad',
  crecimiento: '/crecimiento',
  distribucion: '/distribucion',
  qualitySummary: '/calidad/resumen',
  qualityDedup: '/calidad/dedup',
  qualityNulls: '/calidad/nulls',
  categorias: '/categorias',
  tecnologias: '/tecnologias',
  governanceFreshness: '/governance/freshness',
  governanceCoverage: '/governance/coverage',
  governanceMetrics: '/governance/metrics',
  governanceSample: '/governance/sample',
  governanceReconciliation: '/governance/reconciliation',
};

function buildQuery(filters = {}) {
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value != null && value !== '') {
      if (Array.isArray(value)) {
        value.forEach(v => query.append(key, v));
      } else {
        query.append(key, value);
      }
    }
  });
  const qs = query.toString();
  return qs ? `?${qs}` : '';
}

async function fetchEndpoint(path, qString) {
  const { data } = await axios.get(`${API_BASE_URL}${path}${qString}`);
  return data;
}

export async function fetchKpiData(filters = {}) {
  const cacheKey = CACHE_KEY + JSON.stringify(filters);
  const cached = apiCache.get(cacheKey);

  if (cached && cached.status === 'fresh') {
    return cached.data;
  }

  if (cached && cached.status === 'stale') {
    apiCache._refresh(cacheKey, () => fetchAllEndpoints(filters));
    return cached.data;
  }

  return apiCache.fetch(cacheKey, () => fetchAllEndpoints(filters));
}

async function fetchAllEndpoints(filters) {
  const qString = buildQuery(filters);

  const results = await Promise.allSettled(
    Object.entries(endpoints).map(([key, path]) =>
      fetchEndpoint(path, qString).then(data => ({ key, data }))
    )
  );

  const output = {};
  const errors = [];

  results.forEach(result => {
    if (result.status === 'fulfilled') {
      output[result.value.key] = result.value.data;
    } else {
      errors.push(result.reason?.message || 'Unknown endpoint error');
    }
  });

  if (errors.length > 0) {
    console.warn(`[API] ${errors.length}/${Object.keys(endpoints).length} endpoints failed:`, errors);
  }

  output._apiErrors = errors;

  output.quality = {
    summary: output.qualitySummary,
    dedup: output.qualityDedup,
    nulls: output.qualityNulls
  };

  output.governance = {
    freshness: output.governanceFreshness,
    coverage: output.governanceCoverage,
    metrics: output.governanceMetrics,
    sample: output.governanceSample,
    reconciliation: output.governanceReconciliation,
  };

  return output;
}

export async function fetchAdopcion(filters = {}) {
  return apiCache.fetch(`adopcion${JSON.stringify(filters)}`, () =>
    fetchEndpoint('/adopcion', buildQuery(filters))
  );
}

export async function fetchRanking(filters = {}) {
  return apiCache.fetch(`ranking${JSON.stringify(filters)}`, () =>
    fetchEndpoint('/ranking', buildQuery(filters))
  );
}

export async function fetchTendencia(filters = {}) {
  return apiCache.fetch(`tendencia${JSON.stringify(filters)}`, () =>
    fetchEndpoint('/tendencia', buildQuery(filters))
  );
}

export async function fetchCommunityTrend(filters = {}) {
  const communityFilters = { ...filters, excluir_catalogo: true };
  return apiCache.fetch(`tendenciaComunidad${JSON.stringify(communityFilters)}`, () =>
    fetchEndpoint('/tendencia', buildQuery(communityFilters))
  );
}

export async function fetchMatriz(filters = {}) {
  return apiCache.fetch(`matriz${JSON.stringify(filters)}`, () =>
    fetchEndpoint('/matriz_cobertura', buildQuery(filters))
  );
}

export async function fetchQualitySummary(filters = {}) {
  return apiCache.fetch(`qualitySummary${JSON.stringify(filters)}`, () =>
    fetchEndpoint('/calidad/resumen', buildQuery(filters))
  );
}

export async function fetchQualityDedup(filters = {}) {
  return apiCache.fetch(`qualityDedup${JSON.stringify(filters)}`, () =>
    fetchEndpoint('/calidad/dedup', buildQuery(filters))
  );
}

export async function fetchFilterOptions() {
  return apiCache.fetch('filterOptions', () =>
    fetchEndpoint('/filtros_opciones', '')
  );
}

export async function fetchGovernanceFreshness(runId) {
  const qs = runId ? `?run_id=${encodeURIComponent(runId)}` : '';
  return apiCache.fetch(`governance_freshness${runId || 'latest'}`, () =>
    fetchEndpoint('/governance/freshness', qs)
  );
}

export async function fetchGovernanceCoverage(runId) {
  const qs = runId ? `?run_id=${encodeURIComponent(runId)}` : '';
  return apiCache.fetch(`governance_coverage${runId || 'latest'}`, () =>
    fetchEndpoint('/governance/coverage', qs)
  );
}

export async function fetchGovernanceReconciliation(runId) {
  const qs = runId ? `?run_id=${encodeURIComponent(runId)}` : '';
  return apiCache.fetch(`governance_reconciliation${runId || 'latest'}`, () =>
    fetchEndpoint('/governance/reconciliation', qs)
  );
}
