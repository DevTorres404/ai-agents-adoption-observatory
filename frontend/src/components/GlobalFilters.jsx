import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  CalendarDays,
  Check,
  ChevronDown,
  Filter,
  RotateCcw,
  Search,
  SlidersHorizontal,
  Users,
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

const GlobalFilters = ({ currentFilters, onApplyFilters, onClearFilters }) => {
  const [localFilters, setLocalFilters] = useState(currentFilters);
  const [options, setOptions] = useState(EMPTY_OPTIONS);
  const [optionsState, setOptionsState] = useState('loading');
  const [showAgentes, setShowAgentes] = useState(false);
  const [isExpanded, setIsExpanded] = useState(true);
  const [agentSearch, setAgentSearch] = useState('');
  const multiSelectRef = useRef(null);

  useEffect(() => {
    let mounted = true;
    setOptionsState('loading');
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
    const handleClickOutside = (event) => {
      if (multiSelectRef.current && !multiSelectRef.current.contains(event.target)) {
        setShowAgentes(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const selectedAgentes = localFilters.agentes || [];
  const activeCount = countFilters(currentFilters);
  const pendingCount = countFilters(localFilters);
  const dateError = Boolean(
    localFilters.fecha_inicio &&
    localFilters.fecha_fin &&
    localFilters.fecha_inicio > localFilters.fecha_fin
  );
  const hasChanges = JSON.stringify(compactFilters(localFilters)) !== JSON.stringify(compactFilters(currentFilters));

  const filteredAgents = useMemo(() => {
    const query = agentSearch.trim().toLocaleLowerCase();
    if (!query) return options.agentes;
    return options.agentes.filter(agent => agent.toLocaleLowerCase().includes(query));
  }, [agentSearch, options.agentes]);

  const handleChange = ({ target: { name, value } }) => {
    setLocalFilters(prev => ({ ...prev, [name]: value }));
  };

  const toggleAgente = (agente) => {
    setLocalFilters(prev => {
      const current = prev.agentes || [];
      return {
        ...prev,
        agentes: current.includes(agente)
          ? current.filter(item => item !== agente)
          : [...current, agente]
      };
    });
  };

  const removeAgente = (agente) => {
    setLocalFilters(prev => ({
      ...prev,
      agentes: (prev.agentes || []).filter(item => item !== agente)
    }));
  };

  const clearAll = () => {
    setLocalFilters({});
    setAgentSearch('');
    setShowAgentes(false);
    onClearFilters();
  };

  const applyFilters = () => {
    if (dateError) return;
    onApplyFilters(compactFilters(localFilters));
    setShowAgentes(false);
  };

  const renderSelect = (name, label, values, allLabel) => (
    <div className="filter-group">
      <label htmlFor={`filter-${name}`}>{label}</label>
      <select id={`filter-${name}`} name={name} value={localFilters[name] || ''} onChange={handleChange}>
        <option value="">{allLabel}</option>
        {values.map(value => <option key={value} value={value}>{value}</option>)}
      </select>
    </div>
  );

  return (
    <section className={`panel filters-panel ${isExpanded ? 'is-expanded' : ''}`} aria-label="Filtros globales">
      <div className="filters-header">
        <button className="filters-title-button" onClick={() => setIsExpanded(prev => !prev)} aria-expanded={isExpanded}>
          <span className="filters-icon"><SlidersHorizontal size={19} /></span>
          <span className="filters-title-copy">
            <strong>Explorar datos</strong>
            <small>{activeCount ? `${activeCount} filtro${activeCount === 1 ? '' : 's'} activo${activeCount === 1 ? '' : 's'}` : 'Vista completa del dataset'}</small>
          </span>
          <ChevronDown className="filters-chevron" size={19} />
        </button>
        {activeCount > 0 && (
          <button className="clear-filters-button" onClick={clearAll}>
            <RotateCcw size={15} /> Limpiar todo
          </button>
        )}
      </div>

      {isExpanded && (
        <div className="filters-body">
          <div className="filter-section period-section">
            <div className="filter-section-heading">
              <CalendarDays size={17} />
              <div><strong>Periodo</strong><span>Delimita el rango de observación</span></div>
            </div>
            <div className="date-range">
              <div className="filter-group">
                <label htmlFor="filter-fecha-inicio">Desde</label>
                <input
                  id="filter-fecha-inicio"
                  type="date"
                  name="fecha_inicio"
                  max={localFilters.fecha_fin || undefined}
                  value={localFilters.fecha_inicio || ''}
                  onChange={handleChange}
                />
              </div>
              <span className="date-separator">—</span>
              <div className="filter-group">
                <label htmlFor="filter-fecha-fin">Hasta</label>
                <input
                  id="filter-fecha-fin"
                  type="date"
                  name="fecha_fin"
                  min={localFilters.fecha_inicio || undefined}
                  value={localFilters.fecha_fin || ''}
                  onChange={handleChange}
                />
              </div>
            </div>
            {dateError && <p className="filter-error">La fecha inicial debe ser anterior a la fecha final.</p>}
          </div>

          <div className="filter-section segmentation-section">
            <div className="filter-section-heading">
              <Filter size={17} />
              <div><strong>Segmentación</strong><span>Combina dimensiones del modelo Gold</span></div>
            </div>
            <div className="segmentation-grid">
              {renderSelect('fuente', 'Fuente', options.fuentes, 'Todas las fuentes')}
              {renderSelect('categoria', 'Categoría', options.categorias, 'Todas las categorías')}
              {renderSelect('plataforma', 'Plataforma', options.plataformas, 'Todas las plataformas')}
              {renderSelect('tecnologia', 'Tecnología', options.tecnologias, 'Todas las tecnologías')}
            </div>
          </div>

          <div className="filter-section agents-section" ref={multiSelectRef}>
            <div className="filter-section-heading">
              <Users size={17} />
              <div><strong>Agentes</strong><span>Compara uno o varios agentes de IA</span></div>
            </div>
            <div className="agent-selector">
              <button
                type="button"
                className={`multi-select-trigger ${showAgentes ? 'is-open' : ''}`}
                onClick={() => setShowAgentes(prev => !prev)}
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
                      <button onClick={() => setLocalFilters(prev => ({ ...prev, agentes: [] }))}>Quitar selección</button>
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
                    {filteredAgents.length === 0 && <p className="empty-agent-results">No se encontraron agentes.</p>}
                  </div>
                </div>
              )}
            </div>
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
          </div>

          <div className="filters-footer">
            <div className={`filter-data-status ${optionsState}`}>
              <span className="status-indicator" />
              {optionsState === 'loading' && 'Cargando dimensiones...'}
              {optionsState === 'ready' && `${options.agentes.length} agentes · ${options.fuentes.length} fuentes disponibles`}
              {optionsState === 'error' && 'No se pudieron cargar todas las opciones'}
            </div>
            <div className="filter-actions">
              {hasChanges && <span className="pending-label">Cambios sin aplicar</span>}
              <button className="btn btn-secondary" onClick={() => setLocalFilters(currentFilters)}>Deshacer</button>
              <button className="btn btn-primary" onClick={applyFilters} disabled={dateError || !hasChanges}>
                Aplicar {pendingCount > 0 ? `(${pendingCount})` : ''}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

export default GlobalFilters;
