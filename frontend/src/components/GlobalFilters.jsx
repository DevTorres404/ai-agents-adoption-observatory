import React, { useState, useEffect, useRef } from 'react';
import { Filter, X } from 'lucide-react';
import { fetchFilterOptions } from '../services/api';

const GlobalFilters = ({ currentFilters, onApplyFilters, onClearFilters }) => {
  const [localFilters, setLocalFilters] = useState(currentFilters);
  const [options, setOptions] = useState({ categorias: [], fuentes: [], agentes: [] });
  const [showAgentes, setShowAgentes] = useState(false);
  const multiSelectRef = useRef(null);

  useEffect(() => {
    fetchFilterOptions().then(data => setOptions(data)).catch(console.error);
  }, []);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (multiSelectRef.current && !multiSelectRef.current.contains(e.target)) {
        setShowAgentes(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleChange = (e) => {
    const { name, value, type } = e.target;
    setLocalFilters(prev => ({
      ...prev,
      [name]: type === 'number' ? Number(value) : value
    }));
  };

  const toggleAgente = (agente) => {
    setLocalFilters(prev => {
      const current = prev.agentes || [];
      return {
        ...prev,
        agentes: current.includes(agente)
          ? current.filter(a => a !== agente)
          : [...current, agente]
      };
    });
  };

  const removeAgente = (agente) => {
    setLocalFilters(prev => ({
      ...prev,
      agentes: (prev.agentes || []).filter(a => a !== agente)
    }));
  };

  const handleApply = () => {
    onApplyFilters(localFilters);
  };

  const selectedAgentes = localFilters.agentes || [];

  return (
    <div className="panel filters-panel">
      <div className="filters-header">
        <Filter size={18} color="var(--primary)" />
        <h3>Filtros Globales</h3>
      </div>
      
      <div className="filters-grid">
        <div className="filter-group">
          <label>Fecha Inicio</label>
          <input type="date" name="fecha_inicio" value={localFilters.fecha_inicio || ''} onChange={handleChange} />
        </div>
        
        <div className="filter-group">
          <label>Fecha Fin</label>
          <input type="date" name="fecha_fin" value={localFilters.fecha_fin || ''} onChange={handleChange} />
        </div>

        <div className="filter-group" style={{ position: 'relative' }} ref={multiSelectRef}>
          <label>Agentes</label>
          <div className="multi-select-trigger" onClick={() => setShowAgentes(!showAgentes)}>
            <span className="multi-select-placeholder">
              {selectedAgentes.length > 0
                ? `${selectedAgentes.length} agente(s) seleccionado(s)`
                : 'Seleccionar agentes...'}
            </span>
            <span className="multi-select-arrow">{showAgentes ? '▲' : '▼'}</span>
          </div>
          <div className="multi-select-tags">
            {selectedAgentes.map(a => (
              <span key={a} className="multi-select-tag">
                {a}
                <X size={14} onClick={() => removeAgente(a)} style={{ cursor: 'pointer', marginLeft: '4px' }} />
              </span>
            ))}
          </div>
              {showAgentes && (
            <div className="multi-select-dropdown">
              {(options.agentes || []).map(agente => (
                <label key={agente} className="multi-select-option">
                  <input
                    type="checkbox"
                    checked={selectedAgentes.includes(agente)}
                    onChange={() => toggleAgente(agente)}
                  />
                  <span>{agente}</span>
                </label>
              ))}
            </div>
          )}
        </div>

        <div className="filter-group">
          <label>Fuente</label>
          <select name="fuente" value={localFilters.fuente || ''} onChange={handleChange}>
            <option value="">Todas</option>
            {options.fuentes.map(f => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>

        <div className="filter-actions">
          <button className="btn btn-primary" onClick={handleApply}>Aplicar</button>
          <button className="btn btn-secondary" onClick={() => { setLocalFilters({}); onClearFilters(); }}>Limpiar</button>
        </div>
      </div>
    </div>
  );
};

export default GlobalFilters;
