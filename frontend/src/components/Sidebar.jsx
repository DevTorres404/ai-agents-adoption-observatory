import React from 'react';
import {
  Activity,
  BarChart3,
  ChevronRight,
  Cpu,
  LayoutDashboard,
  Layers,
  Menu,
  Moon,
  ShieldCheck,
  Sun,
  X
} from 'lucide-react';

const NAV_GROUPS = [
  {
    label: 'Análisis',
    items: [
      { id: 'ejecutivo', label: 'Radar de mercado', icon: Activity },
      { id: 'analytics', label: 'Analítica general', icon: LayoutDashboard },
      { id: 'dimensiones', label: 'Dimensiones', icon: Layers },
      { id: 'tendencias', label: 'Tendencias', icon: BarChart3 }
    ]
  },
  {
    label: 'Operaciones',
    items: [
      { id: 'quality', label: 'Calidad de datos', icon: ShieldCheck }
    ]
  }
];

function Brand() {
  return (
    <div className="sidebar-brand">
      <div className="brand-mark" aria-hidden="true">
        <img src="/img/logo.png" alt="Logo" style={{ width: '28px', height: 'auto' }} />
      </div>
      <div>
        <strong>Observatorio AI</strong>
        <span>Business Intelligence</span>
      </div>
    </div>
  );
}

export default function Sidebar({
  activeTab,
  onNavigate,
  theme,
  onToggleTheme,
  isOpen,
  onOpen,
  onClose
}) {
  return (
    <>
      <header className="mobile-header">
        <button className="icon-button" onClick={onOpen} aria-label="Abrir navegación">
          <Menu size={21} />
        </button>
        <div className="mobile-brand"><Cpu size={19} /><strong>Observatorio AI</strong></div>
        <button className="icon-button" onClick={onToggleTheme} aria-label="Cambiar tema">
          {theme === 'light' ? <Moon size={19} /> : <Sun size={19} />}
        </button>
      </header>

      {isOpen && <button className="sidebar-overlay" onClick={onClose} aria-label="Cerrar navegación" />}

      <aside className={`sidebar ${isOpen ? 'is-open' : ''}`} aria-label="Navegación principal">
        <div className="sidebar-top">
          <Brand />
          <button className="sidebar-close icon-button" onClick={onClose} aria-label="Cerrar navegación">
            <X size={20} />
          </button>
        </div>

        <nav className="sidebar-nav">
          {NAV_GROUPS.map(group => (
            <div className="nav-group" key={group.label}>
              <p className="nav-group-label">{group.label}</p>
              {group.items.map(item => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    className={`sidebar-link ${isActive ? 'active' : ''}`}
                    onClick={() => onNavigate(item.id)}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    <span className="sidebar-link-icon"><Icon size={19} /></span>
                    <span>{item.label}</span>
                    {isActive && <ChevronRight className="sidebar-link-arrow" size={17} />}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          <button className="theme-control" onClick={onToggleTheme}>
            {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
            <span>{theme === 'light' ? 'Modo oscuro' : 'Modo claro'}</span>
          </button>
        </div>
      </aside>
    </>
  );
}
