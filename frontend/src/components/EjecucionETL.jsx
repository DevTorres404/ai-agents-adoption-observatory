import React, { useState, useEffect, useRef } from 'react';
import { Play, Square, RefreshCw, Terminal } from 'lucide-react';
import { runEtl, getEtlStatus, getEtlLogs } from '../services/api';

export default function EjecucionETL() {
  const [status, setStatus] = useState('unknown');
  const [logs, setLogs] = useState('');
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const logsEndRef = useRef(null);

  const fetchStatusAndLogs = async () => {
    try {
      const statusData = await getEtlStatus();
      setStatus(statusData.status || 'unknown');
      
      const logsData = await getEtlLogs();
      setLogs(logsData.logs || 'Sin logs disponibles.');
    } catch (err) {
      console.error('Error al obtener estado ETL:', err);
    }
  };

  useEffect(() => {
    fetchStatusAndLogs();
    const interval = setInterval(fetchStatusAndLogs, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const handleRunPipelineClick = () => {
    setShowModal(true);
  };

  const handleConfirmRun = async () => {
    setShowModal(false);
    setLoading(true);
    try {
      await runEtl();
      setStatus('running');
      fetchStatusAndLogs();
    } catch (err) {
      alert("Error al iniciar el ETL: " + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', height: '100%', minHeight: '600px' }}>
      <div className="panel" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ margin: '0 0 0.5rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Terminal size={20} color="var(--primary)" />
            Control de Extracción (ETL)
          </h2>
          <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
            Inicia y monitorea el proceso completo de extracción, transformación y carga del Observatorio AI.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem', background: 'var(--bg-input)', borderRadius: '2rem', border: '1px solid var(--border-primary)' }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: status === 'running' ? '#10b981' : (status === 'exited' ? '#6b7280' : '#f59e0b') }} />
            <span style={{ fontWeight: 500, textTransform: 'capitalize' }}>{status === 'running' ? 'Corriendo' : (status === 'exited' ? 'Detenido' : status)}</span>
          </div>
          <button 
            onClick={handleRunPipelineClick}
            disabled={status === 'running' || loading}
            style={{ 
              display: 'flex', alignItems: 'center', gap: '0.5rem', 
              padding: '0.75rem 1.5rem', borderRadius: '0.5rem', 
              border: 'none', cursor: status === 'running' || loading ? 'not-allowed' : 'pointer',
              background: status === 'running' || loading ? 'var(--border-primary)' : 'var(--primary)',
              color: '#fff', fontWeight: 600, fontSize: '0.95rem'
            }}
          >
            {loading || status === 'running' ? <RefreshCw size={18} className="spin" /> : <Play size={18} />}
            {status === 'running' ? 'Procesando...' : 'Iniciar Extracción'}
          </button>
        </div>
      </div>

      <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden', border: '1px solid var(--border-primary)' }}>
        <div style={{ padding: '0.75rem 1rem', background: '#111827', color: '#9ca3af', borderBottom: '1px solid #374151', display: 'flex', justifyContent: 'space-between', fontFamily: 'monospace', fontSize: '0.85rem' }}>
          <span>/app/etl_logs/pipeline_run.log</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><RefreshCw size={14} /> Auto-refresh (3s)</span>
        </div>
        <div style={{ flex: 1, background: '#000000', color: '#10b981', padding: '1rem', fontFamily: 'monospace', overflowY: 'auto', fontSize: '0.9rem', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
          {logs}
          <div ref={logsEndRef} />
        </div>
      </div>
      
      <style>{`
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `}</style>

      {showModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.6)', zIndex: 9999,
          display: 'flex', alignItems: 'center', justifyContent: 'center'
        }}>
          <div className="panel" style={{ width: '400px', maxWidth: '90%', padding: '2rem' }}>
            <h3 style={{ marginTop: 0 }}>Confirmar Extracción</h3>
            <p style={{ color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              ¿Estás seguro de que deseas iniciar el pipeline de extracción? <br/><br/>
              Este proceso recopilará nuevos datos y sobrescribirá la información temporal en las bases de datos. Tomará varios minutos en completarse.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', marginTop: '1.5rem' }}>
              <button 
                onClick={() => setShowModal(false)}
                style={{ padding: '0.6rem 1.2rem', borderRadius: '0.5rem', background: 'var(--bg-input)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)', cursor: 'pointer', fontWeight: 500 }}
              >
                Cancelar
              </button>
              <button 
                onClick={handleConfirmRun}
                style={{ padding: '0.6rem 1.2rem', borderRadius: '0.5rem', background: 'var(--primary)', border: 'none', color: '#fff', fontWeight: 600, cursor: 'pointer' }}
              >
                Sí, iniciar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
