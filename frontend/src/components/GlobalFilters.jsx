import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Check,
  ChevronDown,
  Database,
  RotateCcw,
  Search,
  SlidersHorizontal,
  X
} from 'lucide-react';
import { fetchFilterOptions } from '../services/api';
import { formatSourceLabel } from '../utils/labels';

const EMPTY_OPTIONS = {
  categorias: [],
  fuentes: [],
  plataformas: [],
  tecnologias: [],
  agentes: []
};

function compactFilters(filters) {
  return Object.fromEntries(
    Object.entries(filters).filter(([, value]) => (
      Array.isArray(value) ? value.length > 0 : value !== '' && value != null
    ))
  );
}

function countFilters(filters) {
  return Object.values(compactFilters(filters)).reduce(
    (total, value) => total + (Array.isArray(value) ? value.length : 1),
    0
  );
}


const GlobalFilters = ({ currentFilters, onApplyFilters, onClearFilters, onViewDataset, refreshing }) => {
  const [localFilters, setLocalFilters] = useState(currentFilters);
  const [options, setOptions] = useState(EMPTY_OPTIONS);
  const [optionsState, setOptionsState] = useState('loading');
  const [showAgentes, setShowAgentes] = useState(false);
  const [agentSearch, setAgentSearch] = useState('');
  const multiSelectRef = useRef(null);

  useEffect(() => {
    let mounted = true;
    fetchFilterOptions()
      .then(data => {
        if (!mounted) return;
        const merged = { ...EMPTY_OPTIONS, ...data };
        setOptions(merged);
        setOptionsState('ready');
        // Sanitize: remove any selected agents that no longer exist in the valid list.
        setLocalFilters(prev => {
          const validSet = new Set(merged.agentes);
          const cleanAgentes = (prev.agentes || []).filter(a => validSet.has(a));
          if (cleanAgentes.length === (prev.agentes || []).length) return prev;
          const next = { ...prev, agentes: cleanAgentes };
          onApplyFilters(compactFilters(next));
          return compactFilters(next);
        });
      })
      .catch(() => {
        if (mounted) setOptionsState('error');
      });
    return () => { mounted = false; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setLocalFilters(currentFilters);
  }, [currentFilters]);

  useEffect(() => {
    const handleClickOutside = event => {
      if (multiSelectRef.current && !multiSelectRef.current.contains(event.target)) {
        setShowAgentes(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const dateError = Boolean(
    localFilters.fecha_inicio &&
    localFilters.fecha_fin &&
    localFilters.fecha_inicio > localFilters.fecha_fin
  );

  const selectedAgentes = localFilters.agentes || [];
  const activeCount = countFilters(currentFilters);
  const filteredAgents = useMemo(() => {
    const query = agentSearch.trim().toLocaleLowerCase();
    if (!query) return options.agentes;
    return options.agentes.filter(agent => agent.toLocaleLowerCase().includes(query));
  }, [agentSearch, options.agentes]);

  // Aplica el filtro de inmediato (selects, fechas y toggles).
  // No hay inputs de texto que disparen consultas: la búsqueda de agentes filtra
  // solo las opciones del desplegable, por lo que no se necesita debounce.
  const applyFilters = next => {
    const compact = compactFilters(next);
    setLocalFilters(compact);
    onApplyFilters(compact);
  };

  const handleChange = ({ target: { name, value } }) => {
    const next = { ...localFilters, [name]: value };
    const invalidRange = Boolean(
      next.fecha_inicio && next.fecha_fin && next.fecha_inicio > next.fecha_fin
    );
    if (invalidRange) {
      // Mantiene el estado local para mostrar el error sin consultar al backend.
      setLocalFilters(compactFilters(next));
      return;
    }
    applyFilters(next);
  };

  const toggleAgente = agente => {
    const current = localFilters.agentes || [];
    applyFilters({
      ...localFilters,
      agentes: current.includes(agente)
        ? current.filter(item => item !== agente)
        : [...current, agente]
    });
  };

  const removeAgente = agente => {
    applyFilters({
      ...localFilters,
      agentes: (localFilters.agentes || []).filter(item => item !== agente)
    });
  };

  const removeSelectFilter = name => {
    applyFilters({ ...localFilters, [name]: '' });
  };

  const removePeriod = () => {
    const rest = { ...localFilters };
    delete rest.fecha_inicio;
    delete rest.fecha_fin;
    applyFilters(rest);
  };

  const clearAll = () => {
    setLocalFilters({});
    setAgentSearch('');
    setShowAgentes(false);
    onClearFilters();
  };

  const activeChips = [];
  if (localFilters.fecha_inicio || localFilters.fecha_fin) {
    activeChips.push({
      key: 'periodo',
      prefix: 'Periodo',
      text: `${localFilters.fecha_inicio || '…'} → ${localFilters.fecha_fin || '…'}`,
      onRemove: removePeriod,
      aria: 'Quitar filtro de periodo'
    });
  }
  if (localFilters.fuente) {
    activeChips.push({
      key: 'fuente',
      prefix: 'Fuente',
      text: formatSourceLabel(localFilters.fuente),
      onRemove: () => removeSelectFilter('fuente'),
      aria: 'Quitar filtro de fuente'
    });
  }
  if (localFilters.plataforma) {
    activeChips.push({
      key: 'plataforma',
      prefix: 'Plataforma',
      text: localFilters.plataforma,
      onRemove: () => removeSelectFilter('plataforma'),
      aria: 'Quitar filtro de plataforma'
    });
  }
  if (localFilters.tecnologia) {
    activeChips.push({
      key: 'tecnologia',
      prefix: 'Tecnología',
      text: localFilters.tecnologia,
      onRemove: () => removeSelectFilter('tecnologia'),
      aria: 'Quitar filtro de tecnología'
    });
  }
  if (localFilters.categoria) {
    activeChips.push({
      key: 'categoria',
      prefix: 'Categoría',
      text: localFilters.categoria,
      onRemove: () => removeSelectFilter('categoria'),
      aria: 'Quitar filtro de categoría'
    });
  }

  const hasActiveChips = activeChips.length > 0 || selectedAgentes.length > 0;

  const renderSelect = (name, label, values, allLabel, optionLabel = value => value) => (
    <div className="filter-group compact-filter-group">
      <label htmlFor={`filter-${name}`}>{label}</label>
      <select id={`filter-${name}`} name={name} value={localFilters[name] || ''} onChange={handleChange}>
        <option value="">{allLabel}</option>
        {values.map(value => <option key={value} value={value}>{optionLabel(value)}</option>)}
      </select>
    </div>
  );

  const statusLabel = refreshing
    ? 'Aplicando…'
    : activeCount
      ? `${activeCount} activo${activeCount === 1 ? '' : 's'}`
      : 'Sin filtros activos';

  return (
    <section className="panel filters-panel filters-panel-compact" aria-label="Filtros globales">
      <div className="filters-compact-toolbar">
        <div className="filters-compact-title">
          <span className="filters-icon"><SlidersHorizontal size={18} /></span>
          <div>
            <strong>Filtros</strong>
            <span>{statusLabel}</span>
          </div>
        </div>
        <button className="dataset-button" type="button" onClick={onViewDataset}>
          <Database size={16} /> Ver dataset completo
        </button>
      </div>

      <div className="filters-compact-grid">
        <div className="filter-group compact-period-filter">
          <label>Periodo</label>
          <div className="compact-date-range">
            <input
              aria-label="Desde"
              type="date"
              name="fecha_inicio"
              max={localFilters.fecha_fin || undefined}
              value={localFilters.fecha_inicio || ''}
              onChange={handleChange}
            />
            <span>—</span>
            <input
              aria-label="Hasta"
              type="date"
              name="fecha_fin"
              min={localFilters.fecha_inicio || undefined}
              value={localFilters.fecha_fin || ''}
              onChange={handleChange}
            />
          </div>
        </div>

        <div className="filter-group compact-filter-group agents-section" ref={multiSelectRef}>
          <label>Agente</label>
          <div className="agent-selector">
            <button
              type="button"
              className={`multi-select-trigger ${showAgentes ? 'is-open' : ''}`}
              onClick={() => setShowAgentes(previous => !previous)}
              aria-expanded={showAgentes}
            >
              <span>{selectedAgentes.length ? `${selectedAgentes.length} seleccionados` : 'Todos los agentes'}</span>
              <ChevronDown size={17} />
            </button>

            {showAgentes && (
              <div className="multi-select-dropdown">
                <div className="agent-search">
                  <Search size={16} />
                  <input
                    autoFocus
                    type="search"
                    value={agentSearch}
                    onChange={event => setAgentSearch(event.target.value)}
                    placeholder={`Buscar entre ${options.agentes.length} agentes`}
                  />
                </div>
                <div className="agent-options-summary">
                  <span>{filteredAgents.length} resultados</span>
                  {selectedAgentes.length > 0 && (
                    <button onClick={() => applyFilters({ ...localFilters, agentes: [] })}>Quitar selección</button>
                  )}
                </div>
                <div className="agent-options-list">
                  {filteredAgents.map(agente => {
                    const selected = selectedAgentes.includes(agente);
                    return (
                      <label key={agente} className={`multi-select-option ${selected ? 'selected' : ''}`}>
                        <input type="checkbox" checked={selected} onChange={() => toggleAgente(agente)} />
                        <span className="custom-checkbox">{selected && <Check size={13} />}</span>
                        <span>{agente}</span>
                      </label>
                    );
                  })}
                  {filteredAgents.length === 0 && (
                    <p className="empty-agent-results">Sin agentes que coincidan con la búsqueda.</p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {renderSelect('categoria', 'Categoría', options.categorias, 'Todas las categorías')}
        {renderSelect('fuente', 'Fuente', options.fuentes, 'Todas las fuentes', formatSourceLabel)}
        {renderSelect('plataforma', 'Plataforma', options.plataformas, 'Todas las plataformas')}
        {renderSelect('tecnologia', 'Tecnología', options.tecnologias, 'Todas las tecnologías')}

        <button className="reset-filters-button" type="button" onClick={clearAll} disabled={activeCount === 0}>
          <RotateCcw size={16} /> Restablecer
        </button>
      </div>

      {dateError && <p className="filter-error compact-filter-error">La fecha inicial debe ser anterior a la fecha final.</p>}

      {(hasActiveChips || optionsState !== 'ready') && (
        <div className="filters-compact-meta">
          <div className="multi-select-tags" aria-label="Filtros activos">
            {activeChips.map(chip => (
              <span key={chip.key} className="multi-select-tag">
                {chip.prefix && <span className="filter-chip-label">{chip.prefix}: </span>}
                {chip.text}
                <button type="button" onClick={chip.onRemove} aria-label={chip.aria}><X size={13} /></button>
              </span>
            ))}
            {selectedAgentes.map(agente => (
              <span key={agente} className="multi-select-tag">
                {agente}
                <button onClick={() => removeAgente(agente)} aria-label={`Quitar ${agente}`}><X size={13} /></button>
              </span>
            ))}
          </div>
          {optionsState !== 'ready' && (
            <span className={`filter-data-status ${optionsState}`}>
              <span className="status-indicator" />
              {optionsState === 'loading' ? 'Cargando dimensiones…' : 'Opciones incompletas'}
            </span>
          )}
        </div>
      )}
    </section>
  );
};

export default GlobalFilters;