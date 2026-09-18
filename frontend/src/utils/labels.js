// Etiquetas legibles para fuentes del ecosistema.
// Los valores internos (ej. "hackernews", "devto") son los que devuelve el backend;
// estas etiquetas se usan en selects, tablas y gráficos para no exponer IDs internos.
export const SOURCE_LABELS = {
  arxiv: 'arXiv',
  catalogo: 'Catálogo',
  devto: 'Dev.to',
  github: 'GitHub',
  gnews: 'Google News',
  google_trends: 'Google Trends',
  hackernews: 'Hacker News',
  reddit: 'Reddit',
  stackoverflow: 'Stack Overflow'
};

export const formatSourceLabel = source => SOURCE_LABELS[source] || source || 'Sin fuente';