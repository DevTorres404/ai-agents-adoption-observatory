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

const GlobalFilters = ({ currentFilters, onApplyFilters, onClearFilters, onViewDataset }) => {
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
        setOptions({ ...EMPTY_OPTIONS, ...data });
        setOptionsState('ready');
      })
      .catch(() => {
        if (mounted) setOptionsState('error');
      });
    return () => { mounted = false; };
  }, []);

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
  const hasChanges = JSON.stringify(compactFilters(localFilters)) !== JSON.stringify(compactFilters(currentFilters));

  useEffect(() => {
    if (dateError || !hasChanges) return undefined;
    const timeoutId = window.setTimeout(() => {
      onApplyFilters(compactFilters(localFilters));
    }, 320);
    return () => window.clearTimeout(timeoutId);
  }, [dateError, hasChanges, localFilters, onApplyFilters]);

  const selectedAgentes = localFilters.agentes || [];
  const activeCount = countFilters(currentFilters);
  const filteredAgents = useMemo(() => {
    const query = agentSearch.trim().toLocaleLowerCase();
    if (!query) return options.agentes;
    return options.agentes.filter(agent => agent.toLocaleLowerCase().includes(query));
  }, [agentSearch, options.agentes]);

  const handleChange = ({ target: { name, value } }) => {
    setLocalFilters(previous => ({ ...previous, [name]: value }));
  };

  const toggleAgente = agente => {
    setLocalFilters(previous => {
      const current = previous.agentes || [];
      return {
        ...previous,
        agentes: current.includes(agente)
          ? current.filter(item => item !== agente)
          : [...current, agente]
      };
    });
  };

  const removeAgente = agente => {
    setLocalFilters(previous => ({
      ...previous,
      agentes: (previous.agentes || []).filter(item => item !== agente)
    }));
  };

  const clearAll = () => {
    setLocalFilters({});
    setAgentSearch('');
    setShowAgentes(false);
    onClearFilters();
  };

  const renderSelect = (name, label, values, allLabel) => (
    <div className="filter-group compact-filter-group">
      <label htmlFor={`filter-${name}`}>{label}</label>
      <select id={`filter-${name}`} name={name} value={localFilters[name] || ''} onChange={handleChange}>
        <option value="">{allLabel}</option>
        {values.map(value => <option key={value} value={value}>{value}</option>)}
      </select>
    </div>
  );

  return (
    <section className="panel filters-panel filters-panel-compact" aria-label="Filtros globales">
      <div className="filters-compact-toolbar">
        <div className="filters-compact-title">
          <span className="filters-icon"><SlidersHorizontal size={18} /></span>
          <div>
            <strong>Filtros</strong>
            <span>{activeCount ? `${activeCount} activo${activeCount === 1 ? '' : 's'}` : 'Actualización automática'}</span>
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
                    <button onClick={() => setLocalFilters(previous => ({ ...previous, agentes: [] }))}>Quitar selección</button>
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
                </div>
              </div>
            )}
          </div>
        </div>

        {renderSelect('fuente', 'Fuente', options.fuentes, 'Todas las fuentes')}
        {renderSelect('plataforma', 'Plataforma', options.plataformas, 'Todas las plataformas')}
        {renderSelect('tecnologia', 'Tecnología', options.tecnologias, 'Todas las tecnologías')}

        <button className="reset-filters-button" type="button" onClick={clearAll} disabled={activeCount === 0 && !hasChanges}>
          <RotateCcw size={16} /> Restablecer
        </button>
      </div>

      {dateError && <p className="filter-error compact-filter-error">La fecha inicial debe ser anterior a la fecha final.</p>}

      {(selectedAgentes.length > 0 || optionsState !== 'ready') && (
        <div className="filters-compact-meta">
          {selectedAgentes.length > 0 && (
            <div className="multi-select-tags">
              {selectedAgentes.map(agente => (
                <span key={agente} className="multi-select-tag">
                  {agente}
                  <button onClick={() => removeAgente(agente)} aria-label={`Quitar ${agente}`}><X size={13} /></button>
                </span>
              ))}
            </div>
          )}
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
