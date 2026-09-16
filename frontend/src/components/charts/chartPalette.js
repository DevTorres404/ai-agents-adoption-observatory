// Paleta compartida para series categóricas (barras top-N, donuts).
// Se mantiene en un módulo propio para no mezclar constantes con exports de
// componentes en Charts.jsx (regla react/only-export-components / Fast Refresh).
// Respeta el azul primario del tema: --primary = #356ae6.
export const CHART_PALETTE = [
  '#356ae6', '#5b8def', '#7c3aed', '#16a36a', '#b45309',
  '#0ea5e9', '#a78bfa', '#34d399', '#f59e0b', '#64748b'
];
